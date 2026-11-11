import {useEffect,useRef} from 'react';
import {playerFrame} from './bridge';

// Raw binary IPC avoids base64/JSON frame encoding. Only one request is in flight
// and the backend retains only the newest frame, including during fast-forward.
export default function StreamCanvas({active,label,onError}:{active:boolean;label:string;onError:(s:string)=>void}){
 const canvas=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{
  if(!active)return;
  let cancelled=false,request=0,sequence=0;
  const paint=async()=>{
   try{
    const frame=await playerFrame(sequence);
    if(cancelled)return;
    if(frame.byteLength>=16){
     const view=new DataView(frame),next=Number(view.getBigUint64(0,true)),width=view.getUint32(8,true),height=view.getUint32(12,true);
     if(width<1||height<1||width>4096||height>4096||frame.byteLength!==16+width*height*4)throw new Error('Invalid game frame.');
     const element=canvas.current;
     if(element){
      if(element.width!==width||element.height!==height){element.width=width;element.height=height;}
      element.getContext('2d',{alpha:false})?.putImageData(new ImageData(new Uint8ClampedArray(frame,16),width,height),0,0);
      element.dataset.frame=String(next);sequence=next;
     }
    }
    request=requestAnimationFrame(()=>{void paint();});
   }catch(error){if(!cancelled)onError(String(error));}
  };
  void paint();
  return()=>{cancelled=true;cancelAnimationFrame(request);};
 },[active,onError]);
 return <canvas ref={canvas} className="stream-canvas" aria-label={label} data-testid="game-canvas"/>;
}
