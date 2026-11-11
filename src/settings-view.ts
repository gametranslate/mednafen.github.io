import {categories,systems} from './catalog';
import type {Category,Snapshot} from './types';
const key=(scope:string|null)=>'mednafen-play-settings-view:'+(scope??'global');
export function readSettingsView(snapshot:Snapshot,scope:string|null):{system:string;category:Category}{
 const game=snapshot.store.games.find(g=>g.id===(scope??snapshot.running))??snapshot.store.games.slice().sort((a,b)=>(b.lastPlayed??0)-(a.lastPlayed??0))[0];
 const fallback={system:game&&game.system!=='auto'?game.system:'snes',category:'general' as Category};
 try{
  const saved=JSON.parse(localStorage.getItem(key(scope))??'null');
  if(saved&&saved.system!=='auto'&&Object.hasOwn(systems,saved.system)&&categories.some(c=>c.id===saved.category))return saved;
 }catch{}
 return fallback;
}
export function rememberSettingsView(scope:string|null,system:string,category:Category){
 try{localStorage.setItem(key(scope),JSON.stringify({system,category}));}catch{}
}
