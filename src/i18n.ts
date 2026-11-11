import {useSyncExternalStore} from 'react';
import en from './locales/en.json';
import de from './locales/de.json';
import vi from './locales/vi.json';
import fr from './locales/fr.json';
import es from './locales/es.json';
import it from './locales/it.json';
import ko from './locales/ko.json';
import zhTW from './locales/zh-TW.json';
import zhCN from './locales/zh-CN.json';
import ja from './locales/ja.json';
export const languages:Record<string,string>={en:'English',de:'Deutsch',vi:'Tiếng Việt',fr:'Français',es:'Español',it:'Italiano',ko:'한국어','zh-TW':'繁體中文','zh-CN':'简体中文',ja:'日本語'};
const dictionaries:Record<string,Record<string,string>>={en,de,vi,fr,es,it,ko,'zh-TW':zhTW,'zh-CN':zhCN,ja};
let current='en';
const listeners=new Set<()=>void>();
export function setLanguage(lang:string){const next=Object.hasOwn(languages,lang)?lang:'en';if(next!==current){current=next;listeners.forEach(fn=>fn());}document.documentElement.lang=next;}
export function getLanguage(){return current;}
export function useLanguage(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},getLanguage);}
const reverse=new Map(Object.entries(en).map(([key,value])=>[value,key]));
export function t(text:string,args:unknown[]=[]):string{
 if(!args.length){
  const range=text.match(/^Value must be between (.*) and (.*)\.$/);
  if(range)return t('Value must be between {0} and {1}.',range.slice(1));
  const missing=text.match(/^File not found: (.+)$/);
  if(missing)return t('File not found: {0}',missing.slice(1));
  const launch=text.match(/^Unable to start Mednafen: (.+)$/);
  if(launch)return t('Unable to start Mednafen: {0}',launch.slice(1));
 }
 const key=text.trim(),source=reverse.get(key)??key;
 const translated=dictionaries[current]?.[source]??dictionaries.en[source]??key;
 return (text.match(/^\s*/)?.[0]??'')+translated.replace(/\{(\d+)\}/g,(_,n)=>String(args[Number(n)]??'{'+n+'}'))+(text.match(/\s*$/)?.[0]??'');
}
