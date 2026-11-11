import {t} from './i18n';
import {invoke,isTauri} from '@tauri-apps/api/core';
import {open,save} from '@tauri-apps/plugin-dialog';
import {getCurrentWindow} from '@tauri-apps/api/window';
import {getCurrentWebview} from '@tauri-apps/api/webview';
import {listen} from '@tauri-apps/api/event';
import type {Snapshot,Store,Values,Preferences,Game,BiosCheck} from './types';
import {definitions} from './catalog';
import {parseConfig,configText} from './settings-utils.mjs';
export const desktop=isTauri();
export function watchClose(guard:()=>boolean){return getCurrentWindow().onCloseRequested(event=>{if(guard())event.preventDefault();});}
export function closeWindow(){return invoke('quit_app');}
export async function watchDrop(onDrop:(paths:string[])=>void,onHover:(value:boolean)=>void){
 const native=await listen<string[]>('player-file-drop',event=>onDrop(event.payload));
 try{
  const webview=await getCurrentWebview().onDragDropEvent(({payload})=>{
   onHover(payload.type==='enter'||payload.type==='over');
   if(payload.type==='drop')onDrop(payload.paths);
  });
  return()=>{native();webview();};
 }catch(error){native();throw error;}
}
export function prepareDrop(paths:string[]):Promise<{store:Store;game:Game}>{return invoke('prepare_dropped_game',{paths});}
export async function clearLibrary():Promise<Store>{
 if(desktop)return invoke('clear_library');
 const s=readPreview();s.games=[];s.gameSettings={};return writePreview(s);
}
const previewKey='mednafen-play-preview-v1';
const fresh=():Store=>({version:1,games:[],settings:{},gameSettings:{},preferences:{theme:'system',enginePath:'',language:'en'}});
function readPreview():Store{try{const text=localStorage.getItem(previewKey);if(text){const s=JSON.parse(text);s.preferences.language??='en';return s;}}catch{}const s=fresh();if(new URLSearchParams(location.search).has('demo')){s.games=[['Chrono Trigger','snes'],['Castlevania: Symphony of the Night','psx'],['NiGHTS into Dreams','ss'],['Tetris','gb']].map(([title,system],i)=>({id:'sample-'+i,title,system,path:'D:\\Games\\'+title+(system==='snes'?'.sfc':'.cue'),favorite:i===0||i===3,lastPlayed:i===0?Date.now()/1000-86400:null}));}return s;}
function writePreview(s:Store){localStorage.setItem(previewKey,JSON.stringify(s));return s;}
export async function snapshot():Promise<Snapshot>{if(desktop)return invoke('load_snapshot');return{store:readPreview(),dataDir:t("Bản xem trước · dữ liệu trình duyệt"),enginePath:t("Mednafen 1.32.1 · bản desktop"),engineExists:false,running:null,lastError:null};}
export async function saveSettings(scope:string|null,values:Values,preferences:Preferences):Promise<Store>{if(desktop)return invoke('save_settings',{scope,values,preferences:scope?null:preferences});const s=readPreview();if(scope)s.gameSettings[scope]=values;else{s.settings=values;s.preferences=preferences;}return writePreview(s);}
export async function chooseFile(directory=false,extensions?:string[]):Promise<string|null>{if(!desktop)throw new Error(t("Chọn tệp trên máy có trong bản desktop. Bạn vẫn có thể nhập đường dẫn trong bản xem trước."));const result=await open({directory,multiple:false,filters:extensions?[{name:t("Tệp được hỗ trợ"),extensions}]:undefined});return typeof result==='string'?result:null;}
export async function addFiles():Promise<Store|null>{if(!desktop)throw new Error(t("Mở bản desktop để thêm và chạy game trên máy."));const paths=await open({multiple:true,filters:[{name:'Game',extensions:['nes','unf','unif','fds','sfc','smc','gb','gbc','gba','pce','sgx','md','gen','smd','sms','gg','ngp','ngc','ws','wsc','vb','lnx','cue','ccd','toc','m3u','zip','gz','zst','ss','mai','woz','dsk','psf','gsf','ssf']} ]});if(!paths)return null;return invoke('add_games',{paths:Array.isArray(paths)?paths:[paths]});}
export async function addFolder():Promise<Store|null>{const path=await chooseFile(true);return path?invoke('scan_folder',{path}):null;}
export async function updateGame(game:Game):Promise<Store>{if(desktop)return invoke('update_game',{id:game.id,title:game.title,system:game.system,favorite:game.favorite});const s=readPreview();s.games=s.games.map(g=>g.id===game.id?game:g);return writePreview(s);}
export async function removeGame(id:string):Promise<Store>{if(desktop)return invoke('remove_game',{id});const s=readPreview();s.games=s.games.filter(g=>g.id!==id);delete s.gameSettings[id];return writePreview(s);}
export async function launchGame(id:string){if(!desktop)throw new Error(t("Đây là bản xem trước. Bản desktop mở game bằng Mednafen thật."));return invoke('launch_game',{id});}
export async function importSettings():Promise<{values:Values;skipped:string[]}|null>{if(desktop){const path=await chooseFile(false,['cfg','txt']);return path?invoke('import_config',{path}):null;}return new Promise(resolve=>{const input=document.createElement('input');input.type='file';input.accept='.cfg,.txt';input.onchange=async()=>{const file=input.files?.[0];resolve(file?parseConfig(await file.text(),definitions) as {values:Values;skipped:string[]}:null);};input.oncancel=()=>resolve(null);input.click();});}
export async function exportSettings(values:Values){if(desktop){const path=await save({defaultPath:'mednafen-play.cfg',filters:[{name:t("Cấu hình Mednafen"),extensions:['cfg']}]});if(!path)return false;await invoke('export_config',{path,values});}else{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([configText(values)],{type:'text/plain;charset=utf-8'}));a.href=url;a.download='mednafen-play.cfg';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}return true;}
export async function checkBios(values:Values):Promise<BiosCheck[]>{if(!desktop)throw new Error(t("Kiểm tra BIOS hoạt động trong bản desktop, nơi ứng dụng đọc được các tệp đã chọn."));return invoke('check_bios',{values});}
export async function openFolder(kind:string){if(!desktop)throw new Error(t("Mở thư mục bằng bản desktop."));return invoke('open_data_folder',{kind});}
export async function readLog():Promise<string>{return desktop?invoke('get_log'):t("Chưa có phiên chơi trong bản xem trước.");}
export function openBrand(event:React.MouseEvent<HTMLAnchorElement>){if(desktop){event.preventDefault();invoke('open_game_translate').catch(console.error);}}

export async function saveAppearance(values:{theme?:string;language?:string}):Promise<Store>{if(desktop)return invoke('save_appearance',values);const s=readPreview();s.preferences={...s.preferences,...values};return writePreview(s);}
export async function playerBounds(bounds:{x:number;y:number;width:number;height:number},visible:boolean){if(desktop)await invoke('player_bounds',{bounds,visible});}
export async function playerVisible(visible:boolean){if(desktop)await invoke('player_visible',{visible});}
export async function playerFullscreen(value:boolean){if(desktop)await invoke('player_fullscreen',{value});}
export async function playerStatus():Promise<{transport:'native'|'canvas';fullscreen:boolean;embedded:boolean;ready:boolean;frames:number}>{return desktop?invoke('player_status'):{transport:'native',fullscreen:false,embedded:false,ready:false,frames:0};}
export async function playerFrame(after:number):Promise<ArrayBuffer>{return invoke('player_frame',{after});}
export async function stopGame(){return desktop?invoke<boolean>('stop_game'):false;}
export async function focusGame(){if(desktop)await invoke('focus_game');}
export async function gameKey(scancode:number,down:boolean,modifiers:number,character?:number){if(desktop)await invoke('player_key',{scancode,down,modifiers,character});}
export async function releaseGameKeys(){if(desktop)await invoke('player_release_keys');}
export function watchPlayerMenu(callback:()=>void){return listen('player-menu',callback);}
export function openProject(event:React.MouseEvent<HTMLAnchorElement>,key:string){if(desktop){event.preventDefault();invoke('open_project_link',{key}).catch(console.error);}}
