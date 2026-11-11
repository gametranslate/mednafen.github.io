/* GameTranslate window adapter, 2026. Mednafen and the original SDL DLL remain
 * unmodified. All other SDL exports forward to SDL2_original.dll. */
#define WIN32_LEAN_AND_MEAN
#define SDL_MAIN_HANDLED
#define DECLSPEC
#include <windows.h>
#include <shellapi.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "SDL.h"
#include "SDL_syswm.h"

static HMODULE self, original;
static HWND parent, child;
static WNDPROC previous;
static SDL_Window *game_window;
static int logical_w=640, logical_h=480, viewport_w=640, viewport_h=480;
static void (APIENTRY *real_viewport)(int,int,int,int);
static SDL_Surface *soft_surface;
static int background_qa;
static int capture_qa;
static uintptr_t frames;
static wchar_t capture_path[32768];
static unsigned char bridge_keys[SDL_NUM_SCANCODES];
static FARPROC proc(const char *name);
#define REAL(name,type) ((type)proc(name))
static void push_focus(int gained) {
    if(!game_window)return;
    SDL_Event event;memset(&event,0,sizeof(event));
    event.type=SDL_WINDOWEVENT;
    event.window.windowID=REAL("SDL_GetWindowID",Uint32(SDLCALL *)(SDL_Window*))(game_window);
    event.window.event=gained?SDL_WINDOWEVENT_FOCUS_GAINED:SDL_WINDOWEVENT_FOCUS_LOST;
    REAL("SDL_PushEvent",int(SDLCALL *)(SDL_Event*))(&event);
}
/* Mednafen's KBMan consumes SDL events, not SDL_GetKeyboardState. This fallback
 * handles keys received by the WebView after a toolbar click, without OS hooks. */
static void bridge_key(unsigned scancode,int down,Uint16 mods) {
    if(scancode>=SDL_NUM_SCANCODES||!game_window)return;
    if(bridge_keys[scancode]==down)return;
    SDL_Event event;memset(&event,0,sizeof(event));
    if(down)push_focus(1);
    event.type=down?SDL_KEYDOWN:SDL_KEYUP;event.key.state=down?SDL_PRESSED:SDL_RELEASED;
    event.key.windowID=REAL("SDL_GetWindowID",Uint32(SDLCALL *)(SDL_Window*))(game_window);
    event.key.keysym.scancode=(SDL_Scancode)scancode;event.key.keysym.mod=mods;
    event.key.keysym.sym=REAL("SDL_GetKeyFromScancode",SDL_Keycode(SDLCALL *)(SDL_Scancode))((SDL_Scancode)scancode);
    if(REAL("SDL_PushEvent",int(SDLCALL *)(SDL_Event*))(&event)>0)bridge_keys[scancode]=(unsigned char)down;
    if(capture_qa){
        unsigned count=0;for(unsigned i=0;i<SDL_NUM_SCANCODES;i++)count+=bridge_keys[i];
        SetPropW(parent,L"MPQAKeys",(HANDLE)(uintptr_t)count);
        SetPropW(parent,L"MPQALastKey",(HANDLE)(uintptr_t)scancode);
        SetPropW(parent,L"MPQATab",(HANDLE)(uintptr_t)bridge_keys[SDL_SCANCODE_TAB]);
    }
}
static void release_bridge(void) {
    for(unsigned i=0;i<SDL_NUM_SCANCODES;i++)if(bridge_keys[i])bridge_key(i,0,0);
    if(GetFocus()!=child||GetForegroundWindow()!=parent)push_focus(0);
}
static void bridge_text(unsigned value) {
    if(value<32||value>0x10ffff||(value>=0xd800&&value<=0xdfff)||!REAL("SDL_IsTextInputActive",SDL_bool(SDLCALL *)(void))())return;
    wchar_t wide[2];int length=1;
    if(value>0xffff){value-=0x10000;wide[0]=(wchar_t)(0xd800+(value>>10));wide[1]=(wchar_t)(0xdc00+(value&1023));length=2;}else wide[0]=(wchar_t)value;
    SDL_Event event;memset(&event,0,sizeof(event));event.type=SDL_TEXTINPUT;
    event.text.windowID=REAL("SDL_GetWindowID",Uint32(SDLCALL *)(SDL_Window*))(game_window);
    WideCharToMultiByte(CP_UTF8,0,wide,length,event.text.text,sizeof(event.text.text)-1,NULL,NULL);
    REAL("SDL_PushEvent",int(SDLCALL *)(SDL_Event*))(&event);
}
/* Opt-in test-only readback: never activates a window or captures the desktop. */
static void capture_frame(SDL_Surface *surface, int gl) {
    if(!capture_qa || !capture_path[0] || !parent || !RemovePropW(parent,L"MPQACapture"))return;
    FILE *file=NULL; _wfopen_s(&file,capture_path,L"wb"); if(!file)return;
    RECT r;GetClientRect(child,&r);
    int w=gl?r.right:surface->w,h=gl?r.bottom:surface->h;
    unsigned char *pixels=(unsigned char*)calloc((size_t)w*h,4);
    if(gl){
        void (APIENTRY *read_pixels)(int,int,int,int,unsigned int,unsigned int,void*)=(void*)REAL("SDL_GL_GetProcAddress",void*(SDLCALL *)(const char*))("glReadPixels");
        read_pixels(0,0,w,h,0x1908,0x1401,pixels);
    }
    fprintf(file,"P6\n%d %d\n255\n",w,h);
    for(int y=0;y<h;y++)for(int x=0;x<w;x++){
        if(gl)fwrite(pixels+((size_t)(h-y-1)*w+x)*4,1,3,file);
        else{Uint8 rgb[4];Uint32 v=*(Uint32*)((char*)surface->pixels+y*surface->pitch+x*4);
            REAL("SDL_GetRGBA",void(SDLCALL *)(Uint32,const SDL_PixelFormat*,Uint8*,Uint8*,Uint8*,Uint8*))(v,surface->format,&rgb[0],&rgb[1],&rgb[2],&rgb[3]);fwrite(rgb,1,3,file);}
    }
    free(pixels);fclose(file);
}
static FARPROC proc(const char *name) {
    if (!original) {
        wchar_t path[32768]; GetModuleFileNameW(self,path,32768);
        wchar_t *slash=wcsrchr(path,L'\\'); if(slash) slash[1]=0;
        wcscat_s(path,32768,L"SDL2_original.dll");
        original=LoadLibraryExW(path,NULL,LOAD_WITH_ALTERED_SEARCH_PATH);
    }
    return original ? GetProcAddress(original,name) : NULL;
}
static LRESULT CALLBACK game_proc(HWND hwnd,UINT msg,WPARAM w,LPARAM l) {
    if(msg==WM_DROPFILES && parent) {
        HDROP drop=(HDROP)w;
        UINT count=DragQueryFileW(drop,0xffffffff,NULL,0);
        size_t size=1;
        for(UINT i=0;i<count;i++)size+=DragQueryFileW(drop,i,NULL,0)+1;
        if(size<=65536) {
            wchar_t *paths=(wchar_t*)calloc(size,sizeof(wchar_t));
            if(paths) {
                size_t at=0;
                for(UINT i=0;i<count;i++)at+=DragQueryFileW(drop,i,paths+at,(UINT)(size-at))+1;
                COPYDATASTRUCT packet={0x4d504452,(DWORD)(size*sizeof(wchar_t)),paths};
                DWORD_PTR result;
                SendMessageTimeoutW(parent,WM_COPYDATA,(WPARAM)hwnd,(LPARAM)&packet,SMTO_ABORTIFHUNG,1000,&result);
                free(paths);
            }
        }
        DragFinish(drop);return 0;
    }
    if(msg==WM_APP+71){if(!background_qa&&IsWindowVisible(hwnd)&&GetForegroundWindow()==parent)SetFocus(hwnd);return 0;}
    if(msg==WM_APP+73){bridge_key((unsigned)w,(int)(l&1),(Uint16)(l>>16));return 0;}
    if(msg==WM_APP+74){release_bridge();return 0;}
    if(msg==WM_APP+75){bridge_text((unsigned)w);return 0;}
    if(msg==WM_GETDLGCODE)return DLGC_WANTALLKEYS|DLGC_WANTARROWS|DLGC_WANTTAB;
    if(msg==WM_KILLFOCUS||(msg==WM_SHOWWINDOW&&!w))release_bridge();
    if(msg==WM_APP+72 && capture_qa){
        SDL_Event event;memset(&event,0,sizeof(event));
        event.type=SDL_WINDOWEVENT;event.window.windowID=REAL("SDL_GetWindowID",Uint32(SDLCALL *)(SDL_Window*))(game_window);
        event.window.event=SDL_WINDOWEVENT_FOCUS_GAINED;
        REAL("SDL_PushEvent",int(SDLCALL *)(SDL_Event*))(&event);
        event.type=l?SDL_KEYUP:SDL_KEYDOWN;event.key.state=l?SDL_RELEASED:SDL_PRESSED;
        event.key.keysym.scancode=(SDL_Scancode)w;event.key.keysym.sym=REAL("SDL_GetKeyFromScancode",SDL_Keycode(SDLCALL *)(SDL_Scancode))((SDL_Scancode)w);
        REAL("SDL_PushEvent",int(SDLCALL *)(SDL_Event*))(&event);return 0;
    }
    if ((msg==WM_KEYDOWN||msg==WM_SYSKEYDOWN) && !(l&(1L<<30))) {
        if (w==VK_ESCAPE) {
            SetPropW(parent,L"MPRequest",(HANDLE)(uintptr_t)(GetPropW(parent,L"MPFullscreen")?1:3)); return 0;
        }
        if(w==VK_F4 && ((l&(1L<<29))||(GetKeyState(VK_MENU)&0x8000))) {
            PostMessageW(parent,WM_CLOSE,0,0);return 0;
        }
        if (w==VK_RETURN && ((l&(1L<<29)) || (GetKeyState(VK_MENU)&0x8000))) {
            SetPropW(parent,L"MPRequest",(HANDLE)2); return 0;
        }
    }
    return CallWindowProcW(previous,hwnd,msg,w,l);
}
static void fit(void) {
    if (!parent||!child) return;
    int x=(int)(intptr_t)GetPropW(parent,L"MPX"), y=(int)(intptr_t)GetPropW(parent,L"MPY");
    int w=(int)(intptr_t)GetPropW(parent,L"MPW"), h=(int)(intptr_t)GetPropW(parent,L"MPH");
    if(w<1||h<1)return;
    RECT r; GetWindowRect(child,&r); POINT p={r.left,r.top};ScreenToClient(parent,&p);
    if(p.x!=x||p.y!=y||r.right-r.left!=w||r.bottom-r.top!=h)
        SetWindowPos(child,HWND_TOP,x,y,w,h,SWP_NOACTIVATE|SWP_FRAMECHANGED);
}
static void APIENTRY host_viewport(int x,int y,int w,int h) {
    viewport_w=w;viewport_h=h;
    if (parent && child && w>0 && h>0) {
        RECT r;GetClientRect(child,&r);
        double scale=min((double)r.right/w,(double)r.bottom/h);
        int fw=(int)(w*scale),fh=(int)(h*scale);
        real_viewport((r.right-fw)/2,(r.bottom-fh)/2,fw,fh);
    } else real_viewport(x,y,w,h);
}
SDL_Window * SDLCALL SDL_CreateWindow(const char *title,int x,int y,int w,int h,Uint32 flags) {
    GetEnvironmentVariableW(L"MEDNAFEN_PLAY_QA_CAPTURE",capture_path,32768);
    capture_qa=capture_path[0] && GetEnvironmentVariableW(L"MEDNAFEN_PLAY_TEST_HOME",NULL,0)>0;
    background_qa=GetEnvironmentVariableW(L"MEDNAFEN_PLAY_BACKGROUND_QA",NULL,0)>0 && GetEnvironmentVariableW(L"MEDNAFEN_PLAY_TEST_HOME",NULL,0)>0;
    logical_w=w;logical_h=h;
    char env[64]; if(GetEnvironmentVariableA("MEDNAFEN_PLAY_PARENT",env,sizeof(env)))
        parent=(HWND)(uintptr_t)_strtoui64(env,NULL,10);
    if(parent&&!IsWindow(parent))parent=NULL;
    SDL_Window *win=REAL("SDL_CreateWindow",SDL_Window* (SDLCALL *)(const char*,int,int,int,int,Uint32))(title,x,y,w,h,parent?flags|SDL_WINDOW_HIDDEN:flags);
    if(parent&&win) {
        SDL_SysWMinfo info; SDL_VERSION(&info.version);
        if(REAL("SDL_GetWindowWMInfo",SDL_bool (SDLCALL *)(SDL_Window*,SDL_SysWMinfo*))(win,&info)) {
            child=info.info.win.window;game_window=win;
            SetWindowLongPtrW(child,GWL_STYLE,WS_CHILD|WS_CLIPSIBLINGS|WS_CLIPCHILDREN);
            SetWindowLongPtrW(child,GWL_EXSTYLE,0);
            SetParent(child,parent);
            previous=(WNDPROC)SetWindowLongPtrW(child,GWLP_WNDPROC,(LONG_PTR)game_proc);
            SetPropW(parent,L"MPChild",child);
            DragAcceptFiles(child,TRUE);
            frames=0;SetPropW(parent,L"MPFrames",NULL);
            fit();
        }
    }
    return win;
}
void SDLCALL SDL_SetWindowSize(SDL_Window *w,int width,int height) {
    logical_w=width;logical_h=height;
    REAL("SDL_SetWindowSize",void(SDLCALL *)(SDL_Window*,int,int))(w,width,height);fit();
}
void SDLCALL SDL_SetWindowPosition(SDL_Window *w,int x,int y) {
    if(parent)fit();else REAL("SDL_SetWindowPosition",void(SDLCALL *)(SDL_Window*,int,int))(w,x,y);
}
int SDLCALL SDL_SetWindowFullscreen(SDL_Window *w,Uint32 flags) {
    return parent ? 0 : REAL("SDL_SetWindowFullscreen",int(SDLCALL *)(SDL_Window*,Uint32))(w,flags);
}
void SDLCALL SDL_RaiseWindow(SDL_Window *w) {
    if(parent){if(!background_qa && GetForegroundWindow()==parent)SetFocus(child);}
    else REAL("SDL_RaiseWindow",void(SDLCALL *)(SDL_Window*))(w);
}
void * SDLCALL SDL_GL_GetProcAddress(const char *name) {
    void *p=REAL("SDL_GL_GetProcAddress",void*(SDLCALL *)(const char*))(name);
    if(parent&&!strcmp(name,"glViewport")){real_viewport=(void(APIENTRY *)(int,int,int,int))p;return host_viewport;}
    return p;
}
void SDLCALL SDL_GL_SwapWindow(SDL_Window *w) {
    fit();
    if(parent&&real_viewport)host_viewport(0,0,viewport_w,viewport_h);
    capture_frame(NULL,1);
    REAL("SDL_GL_SwapWindow",void(SDLCALL *)(SDL_Window*))(w);
    if(parent)SetPropW(parent,L"MPFrames",(HANDLE)++frames);
}
Uint32 SDLCALL SDL_GetWindowFlags(SDL_Window *w) {
    Uint32 flags=REAL("SDL_GetWindowFlags",Uint32(SDLCALL *)(SDL_Window*))(w);
    if(parent)SetPropW(parent,L"MPSDLFlags",(HANDLE)(uintptr_t)flags);
    return background_qa ? flags&~(SDL_WINDOW_HIDDEN|SDL_WINDOW_MINIMIZED) : flags;
}
void SDLCALL SDL_ShowWindow(SDL_Window *w) {
    if(parent&&background_qa)return;
    REAL("SDL_ShowWindow",void(SDLCALL *)(SDL_Window*))(w);
}
SDL_Surface * SDLCALL SDL_GetWindowSurface(SDL_Window *w) {
    if(!parent)return REAL("SDL_GetWindowSurface",SDL_Surface*(SDLCALL *)(SDL_Window*))(w);
    if(soft_surface&&(soft_surface->w!=logical_w||soft_surface->h!=logical_h)){
        REAL("SDL_FreeSurface",void(SDLCALL *)(SDL_Surface*))(soft_surface);soft_surface=NULL;
    }
    if(!soft_surface)soft_surface=REAL("SDL_CreateRGBSurfaceWithFormat",SDL_Surface*(SDLCALL *)(Uint32,int,int,int,Uint32))(0,logical_w,logical_h,32,SDL_PIXELFORMAT_RGB888);
    return soft_surface;
}
int SDLCALL SDL_UpdateWindowSurface(SDL_Window *w) {
    if(parent&&soft_surface){
        fit();
        SDL_Surface *screen=REAL("SDL_GetWindowSurface",SDL_Surface*(SDLCALL *)(SDL_Window*))(w);
        if(screen){
            double scale=min((double)screen->w/logical_w,(double)screen->h/logical_h);
            SDL_Rect dst={(screen->w-(int)(logical_w*scale))/2,(screen->h-(int)(logical_h*scale))/2,(int)(logical_w*scale),(int)(logical_h*scale)};
            REAL("SDL_FillRect",int(SDLCALL *)(SDL_Surface*,const SDL_Rect*,Uint32))(screen,NULL,0);
            REAL("SDL_UpperBlitScaled",int(SDLCALL *)(SDL_Surface*,const SDL_Rect*,SDL_Surface*,SDL_Rect*))(soft_surface,NULL,screen,&dst);
            capture_frame(screen,0);
        }
    }
    int result=REAL("SDL_UpdateWindowSurface",int(SDLCALL *)(SDL_Window*))(w);
    if(parent&&result==0)SetPropW(parent,L"MPFrames",(HANDLE)++frames);
    return result;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH){self=instance;DisableThreadLibraryCalls(instance);}return TRUE;
}
