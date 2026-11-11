import {useEffect,useRef} from 'react';
import {Maximize,Square,Gamepad2} from 'lucide-react';
import * as api from './bridge';
import type {Game} from './types';
import {t} from './i18n';
import {useGameKeyboard} from './useGameKeyboard';
export default function Player({game,ready,fullscreen,visible,onFullscreen,onStop,onMenu,onQuit,onError}:{game:Game;ready:boolean;fullscreen:boolean;visible:boolean;onFullscreen:()=>void;onStop:()=>void;onMenu:()=>void;onQuit:()=>void;onError:(s:string)=>void}){
 const viewport=useRef<HTMLDivElement>(null);
 useGameKeyboard(visible&&ready,{escape:()=>fullscreen?api.playerFullscreen(false).catch(e=>onError(String(e))):onMenu(),fullscreen:onFullscreen,close:onQuit,error:onError});
 useEffect(()=>{if(visible&&ready)api.focusGame().catch(e=>onError(String(e)));},[visible,ready,fullscreen,onError]);
 useEffect(()=>{
  const el=viewport.current!;
  const update=()=>{const r=el.getBoundingClientRect(),d=window.devicePixelRatio;api.playerBounds({x:Math.round(r.x*d),y:Math.round(r.y*d),width:Math.max(1,Math.round(r.width*d)),height:Math.max(1,Math.round(r.height*d))},visible).catch(e=>onError(String(e)));};
  const observer=new ResizeObserver(update);observer.observe(el);window.addEventListener('resize',update);update();
  return()=>{observer.disconnect();window.removeEventListener('resize',update);};
 },[fullscreen,visible,onError]);
 return <section className="player-view"><div className="player-toolbar"><div><Gamepad2 size={18}/><strong>{game.title}</strong></div><span>{t('Tab: fast-forward · Esc: menu')}</span><button className="button" onClick={onFullscreen}><Maximize size={16}/>{t('Fullscreen')}</button><button className="button" onClick={onStop}><Square size={15}/>{t('Stop game')}</button></div><div ref={viewport} className="player-viewport" data-testid="player-viewport" onClick={()=>api.focusGame()}>{!ready&&<span role="status">{t('Starting game…')}</span>}</div></section>;
}
