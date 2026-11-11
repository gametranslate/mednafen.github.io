export type Values = Record<string,string>;
export type Definition = {key:string; type:string; default:string; description:string; help:string; min:string; max:string; options:{value:string;label:string;description:string}[];flags:string[];aliases:string[]};
export type Game = {id:string;title:string;path:string;system:string;favorite:boolean;lastPlayed:number|null};
export type Preferences={theme:string;enginePath:string;language:string};
export type Store={version:number;games:Game[];settings:Values;gameSettings:Record<string,Values>;preferences:Preferences};
export type Snapshot={store:Store;dataDir:string;enginePath:string;engineExists:boolean;running:string|null;lastError:string|null};
export type BiosCheck={key:string;path:string;exists:boolean;sha256:string|null;matches:boolean|null};
export type Category='general'|'video'|'audio'|'input'|'bios'|'saves'|'folders'|'system'|'network'|'advanced';
