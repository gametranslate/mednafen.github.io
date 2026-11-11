/* GameTranslate Unix display/input adapter. Linked into our Mednafen build;
 * emulation sources are unchanged. SDL still owns audio and game controllers.
 * Frames travel through a private Unix socket to the application's canvas.
 * No foreign window reparenting, visible SDL window or desktop input hooks. */
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include <dlfcn.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static int connection = -1, active, disconnected;
static SDL_Window *window;
static uint8_t held[SDL_NUM_SCANCODES], command[16];
static size_t command_used;
static uint64_t frames;
static Uint32 last_capture;
static uint8_t *pixels, *row;
static size_t pixel_capacity, row_capacity;
#define REAL(name, type) ((type)resolve(name))
static void *resolve(const char *name) {
    void *p = dlsym(RTLD_NEXT, name);
    if (!p) { fprintf(stderr, "Display adapter: missing %s\n", name); abort(); }
    return p;
}
static void put32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24);
}
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void push(SDL_Event *event) {
    REAL("SDL_PushEvent", int (*)(SDL_Event *))(event);
}
static void quit(void) {
    if (disconnected) return;
    disconnected=1;
    SDL_Event event; memset(&event,0,sizeof(event)); event.type=SDL_QUIT; push(&event);
}
static int write_all(const void *data, size_t count) {
    const uint8_t *p=data;
    while (count) {
#ifdef MSG_NOSIGNAL
        ssize_t n=send(connection,p,count,MSG_NOSIGNAL);
#else
        ssize_t n=send(connection,p,count,0);
#endif
        if (n<0 && errno==EINTR) continue;
        if (n<=0) { quit(); return 0; }
        p+=n; count-=(size_t)n;
    }
    return 1;
}
static void focus(void) {
    SDL_Event event; memset(&event,0,sizeof(event));
    event.type=SDL_WINDOWEVENT;
    event.window.windowID=REAL("SDL_GetWindowID", Uint32 (*)(SDL_Window *))(window);
    event.window.event=SDL_WINDOWEVENT_FOCUS_GAINED; push(&event);
}
static void key(uint32_t code, int down, Uint16 mods, uint32_t character) {
    if (!window || code>=SDL_NUM_SCANCODES || held[code]==down) return;
    if (down) focus();
    SDL_Event event; memset(&event,0,sizeof(event));
    event.type=down?SDL_KEYDOWN:SDL_KEYUP;
    event.key.state=down?SDL_PRESSED:SDL_RELEASED;
    event.key.windowID=REAL("SDL_GetWindowID", Uint32 (*)(SDL_Window *))(window);
    event.key.keysym.scancode=(SDL_Scancode)code;
    event.key.keysym.sym=REAL("SDL_GetKeyFromScancode", SDL_Keycode (*)(SDL_Scancode))((SDL_Scancode)code);
    event.key.keysym.mod=mods; push(&event); held[code]=(uint8_t)down;
    if (down && character>=32 && character<=0x10ffff && !(character>=0xd800 && character<=0xdfff)
        && REAL("SDL_IsTextInputActive", SDL_bool (*)(void))()) {
        memset(&event,0,sizeof(event)); event.type=SDL_TEXTINPUT;
        event.text.windowID=REAL("SDL_GetWindowID", Uint32 (*)(SDL_Window *))(window);
        uint8_t *p=(uint8_t *)event.text.text;
        if(character<0x80)p[0]=character;
        else if(character<0x800){p[0]=0xc0|(character>>6);p[1]=0x80|(character&63);}
        else if(character<0x10000){p[0]=0xe0|(character>>12);p[1]=0x80|((character>>6)&63);p[2]=0x80|(character&63);}
        else{p[0]=0xf0|(character>>18);p[1]=0x80|((character>>12)&63);p[2]=0x80|((character>>6)&63);p[3]=0x80|(character&63);}
        push(&event);
    }
}
static void controls(void) {
    if (connection<0 || disconnected) return;
    for (;;) {
        ssize_t n=recv(connection,command+command_used,sizeof(command)-command_used,MSG_DONTWAIT);
        if (n<0 && errno==EINTR) continue;
        if (n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) return;
        if (n<=0) { quit(); return; }
        command_used+=(size_t)n;
        if (command_used!=sizeof(command)) continue;
        command_used=0;
        uint32_t kind=get32(command),code=get32(command+4),flags=get32(command+8);
        if(kind==1)key(code,flags&1,(Uint16)(flags>>16),get32(command+12));
        else if(kind==2){for(unsigned i=0;i<SDL_NUM_SCANCODES;i++)if(held[i])key(i,0,0,0);}
        else if(kind==3)quit();
    }
}
static void connect_host(void) {
    const char *path=getenv("MEDNAFEN_PLAY_SOCKET");
    if (!path || active) return;
    active=1;
    struct sockaddr_un address; memset(&address,0,sizeof(address)); address.sun_family=AF_UNIX;
    if (strlen(path)>=sizeof(address.sun_path)) { fprintf(stderr,"Display socket path too long\n"); exit(1); }
    strcpy(address.sun_path,path);
    connection=socket(AF_UNIX,SOCK_STREAM,0);
    if(connection<0 || connect(connection,(struct sockaddr *)&address,sizeof(address))!=0){perror("Display socket");exit(1);}
    struct timeval timeout={2,0}; setsockopt(connection,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
#ifdef SO_NOSIGPIPE
    int enabled=1; setsockopt(connection,SOL_SOCKET,SO_NOSIGPIPE,&enabled,sizeof(enabled));
#endif
    uint8_t hello[8]={'M','P','H','1',0,0,0,0}; put32(hello+4,(uint32_t)getpid());
    if(!write_all(hello,sizeof(hello)))exit(1);
}
SDL_Window *SDL_CreateWindow(const char *title,int x,int y,int w,int h,Uint32 flags) {
    connect_host();
    window=REAL("SDL_CreateWindow", SDL_Window *(*)(const char *,int,int,int,int,Uint32))(
        title,x,y,w,h,active?(flags|SDL_WINDOW_HIDDEN)&~SDL_WINDOW_SHOWN:flags);
    if(active && window)focus();
    return window;
}
void SDL_ShowWindow(SDL_Window *w) { if(!active)REAL("SDL_ShowWindow",void (*)(SDL_Window *))(w); }
void SDL_RaiseWindow(SDL_Window *w) { if(!active)REAL("SDL_RaiseWindow",void (*)(SDL_Window *))(w); }
int SDL_SetWindowFullscreen(SDL_Window *w,Uint32 flags) {
    return active?0:REAL("SDL_SetWindowFullscreen",int (*)(SDL_Window *,Uint32))(w,flags);
}
void SDL_SetWindowGrab(SDL_Window *w,SDL_bool grab) {
    if(!active)REAL("SDL_SetWindowGrab",void (*)(SDL_Window *,SDL_bool))(w,grab);
}
int SDL_SetRelativeMouseMode(SDL_bool value) {
    return active?0:REAL("SDL_SetRelativeMouseMode",int (*)(SDL_bool))(value);
}
Uint32 SDL_GetWindowFlags(SDL_Window *w) {
    Uint32 flags=REAL("SDL_GetWindowFlags",Uint32 (*)(SDL_Window *))(w);
    return active?(flags&~(SDL_WINDOW_HIDDEN|SDL_WINDOW_MINIMIZED))|SDL_WINDOW_INPUT_FOCUS:flags;
}
int SDL_PollEvent(SDL_Event *event) {
    controls();
    for (;;) {
        int found=REAL("SDL_PollEvent",int (*)(SDL_Event *))(event);
        if(!active || !found || !event)return found;
        if(event->type==SDL_WINDOWEVENT && (event->window.event==SDL_WINDOWEVENT_FOCUS_LOST ||
            event->window.event==SDL_WINDOWEVENT_HIDDEN || event->window.event==SDL_WINDOWEVENT_MINIMIZED))continue;
        return found;
    }
}
static int buffer(int width,int height) {
    if(width<1 || height<1 || width>4096 || height>4096)return 0;
    size_t length=(size_t)width*height*4;
    if(length>pixel_capacity){void *p=realloc(pixels,length);if(!p)return 0;pixels=p;pixel_capacity=length;}
    if((size_t)width*4>row_capacity){void *p=realloc(row,(size_t)width*4);if(!p)return 0;row=p;row_capacity=(size_t)width*4;}
    return 1;
}
static int capture_due(void) {
    if(!active || disconnected)return 0;
    ++frames;
    Uint32 now=REAL("SDL_GetTicks",Uint32 (*)(void))();
    if(frames>1 && now-last_capture<16)return 0;
    last_capture=now;return 1;
}
static void publish(int width,int height) {
    uint8_t header[24]={'M','P','F','1'};
    put32(header+4,width);put32(header+8,height);put32(header+12,(uint32_t)width*height*4);
    put32(header+16,(uint32_t)frames);put32(header+20,(uint32_t)(frames>>32));
    if(write_all(header,sizeof(header)))write_all(pixels,(size_t)width*height*4);
}
void SDL_GL_SwapWindow(SDL_Window *w) {
    if(capture_due()) {
        int width=0,height=0;
        REAL("SDL_GL_GetDrawableSize",void (*)(SDL_Window *,int *,int *))(w,&width,&height);
        if(buffer(width,height)) {
            void *(*getproc)(const char *)=REAL("SDL_GL_GetProcAddress",void *(*)(const char *));
            void (*readpixels)(int,int,int,int,unsigned,unsigned,void *)=(void *)getproc("glReadPixels");
            void (*store)(unsigned,int)=(void *)getproc("glPixelStorei");
            void (*get)(unsigned,int *)=(void *)getproc("glGetIntegerv");
            int alignment=4,rowlength=0,skiprows=0,skippixels=0;
            get(0x0D05,&alignment);get(0x0D02,&rowlength);get(0x0D03,&skiprows);get(0x0D04,&skippixels);
            store(0x0D05,4);store(0x0D02,0);store(0x0D03,0);store(0x0D04,0);
            readpixels(0,0,width,height,0x1908,0x1401,pixels);
            store(0x0D05,alignment);store(0x0D02,rowlength);store(0x0D03,skiprows);store(0x0D04,skippixels);
            size_t pitch=(size_t)width*4;
            for(int y=0;y<height/2;y++){
                uint8_t *top=pixels+y*pitch,*bottom=pixels+(height-y-1)*pitch;
                memcpy(row,top,pitch);memcpy(top,bottom,pitch);memcpy(bottom,row,pitch);
            }
            for(size_t i=3;i<(size_t)height*pitch;i+=4)pixels[i]=255;
            publish(width,height);
        }
    }
    REAL("SDL_GL_SwapWindow",void (*)(SDL_Window *))(w);
}
int SDL_UpdateWindowSurface(SDL_Window *w) {
    if(capture_due()) {
        SDL_Surface *surface=REAL("SDL_GetWindowSurface",SDL_Surface *(*)(SDL_Window *))(w);
        if(surface && buffer(surface->w,surface->h)) {
            int locked=REAL("SDL_LockSurface",int (*)(SDL_Surface *))(surface);
            if(locked==0){
                int ok=REAL("SDL_ConvertPixels",int (*)(int,int,Uint32,const void *,int,Uint32,void *,int))(
                    surface->w,surface->h,surface->format->format,surface->pixels,surface->pitch,SDL_PIXELFORMAT_RGBA32,pixels,surface->w*4);
                REAL("SDL_UnlockSurface",void (*)(SDL_Surface *))(surface);
                if(ok==0){for(size_t i=3;i<(size_t)surface->w*surface->h*4;i+=4)pixels[i]=255;publish(surface->w,surface->h);}
            }
        }
    }
    return active?0:REAL("SDL_UpdateWindowSurface",int (*)(SDL_Window *))(w);
}
