import {useEffect,useRef} from 'react';
import {SDL_CODES} from './settings-utils.mjs';
import * as api from './bridge';

type Actions={escape:()=>void;fullscreen:()=>void;close:()=>void;error:(s:string)=>void};
// Only the visible game owns these events. Settings/dialogs retain normal typing
// and Tab navigation; OS shortcuts are never globally hooked or grabbed.
export function useGameKeyboard(active:boolean,actions:Actions){
 const latest=useRef(actions);latest.current=actions;
 useEffect(()=>{
  if(!active)return;
  let queue=Promise.resolve();
  const send=(work:()=>Promise<unknown>)=>{queue=queue.then(work).then(()=>{},e=>latest.current.error(String(e)));};
  const release=()=>send(()=>api.releaseGameKeys());
  const key=(e:KeyboardEvent)=>{
   if(e.metaKey||e.code.startsWith('Meta')||(e.altKey&&e.code==='Tab')){release();return;}
   e.preventDefault();e.stopImmediatePropagation();
   const down=e.type==='keydown';
   if(e.code==='Escape') {if(down&&!e.repeat){release();latest.current.escape();}return;}
   if(e.altKey&&(e.code==='Enter'||e.code==='F4')){
    if(down&&!e.repeat){release();e.code==='F4'?latest.current.close():latest.current.fullscreen();}return;
   }
   const scancode=SDL_CODES[e.code as keyof typeof SDL_CODES];
   if(scancode===undefined)return;
   const modifiers=(e.shiftKey?3:0)|(e.ctrlKey?192:0)|(e.altKey?768:0);
   const character=down&&!e.ctrlKey&&!e.altKey&&[...e.key].length===1?e.key.codePointAt(0):undefined;
   send(()=>api.gameKey(scancode,down,modifiers,character));
  };
  const visibility=()=>{if(document.hidden)release();};
  window.addEventListener('keydown',key,true);window.addEventListener('keyup',key,true);
  window.addEventListener('blur',release);document.addEventListener('visibilitychange',visibility);
  return()=>{window.removeEventListener('keydown',key,true);window.removeEventListener('keyup',key,true);window.removeEventListener('blur',release);document.removeEventListener('visibilitychange',visibility);release();};
 },[active]);
}
