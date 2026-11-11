import {t} from './i18n';
import {useEffect,useRef,type ReactNode} from 'react';
import {X} from 'lucide-react';
export function Modal({title,children,onClose,wide=false}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const d=ref.current!;if(!d.open)d.showModal();return()=>d.close();},[]);
 return <dialog ref={ref} className={'dialog '+(wide?'dialog-wide':'')} aria-label={title} onCancel={e=>{e.preventDefault();onClose();}}><header><h2>{title}</h2><button className="icon-button" aria-label={t("Đóng")} onClick={onClose}><X size={18}/></button></header>{children}</dialog>;
}
