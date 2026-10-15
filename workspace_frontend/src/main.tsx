import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import DataGrid from './data-grid';
import {setRole,acceptResponse} from './bridge';
import type {Cell} from './grid-utils';
import './globals.css';
import './workspace.css';
type Args={headers:string[];rows:Cell[][];title:string;description?:string;role:string;permissions?:Record<string,boolean>;response?:{id:string;ok:boolean;error?:string};storageKey:string};
function Workspace({args}:{args:Args}){
 const [selected,setSelected]=useState<Cell[]|null>(null);
 return <div className="workspace-table"><div className="paneltitle"><div><h2>{args.title}</h2><p>{args.description}</p></div><span>Open any record for details</span></div><DataGrid headers={args.headers} rows={args.rows} storageKey={args.storageKey} filename={args.title} onCell={r=>setSelected(r)}/>{selected&&<div className="row-detail" role="dialog" aria-modal="true" aria-label="Full-window record details"><div className="detailtopbar"><button className="secondary" onClick={()=>setSelected(null)}>← Back to table</button><h2>Record details</h2></div><dl>{args.headers.map((h,i)=><div key={h}><dt>{h}</dt><dd>{String(selected[i]??'—').split(/(https?:\/\/[^\s]+)/g).map((s,j)=>/^https?:\/\//.test(s)?<a key={j} href={s} target="_blank" rel="noreferrer">{s}</a>:s)}</dd></div>)}</dl></div>}</div>
}
const root=createRoot(document.getElementById('root')!);
const send=(type:string,extra:Record<string,unknown>)=>window.parent.postMessage({isStreamlitMessage:true,type,...extra},'*');
let height=0;
// Size the embedded frame for ten complete rows, independently of screen height.
// A short viewport should scroll the page rather than squash the result table.
function fit(){
 const table=document.querySelector('.workspace-table');
 const firstRows=Array.from(document.querySelectorAll('.gridtable tbody tr')).slice(0,10);
 const rowHeight=firstRows.reduce((sum,row)=>sum+row.getBoundingClientRect().height,0);
 const chrome=Array.from(document.querySelectorAll('.paneltitle,.gridtools,.gridtable thead,.pagination,.gridnote,.gridtable tfoot')).reduce((sum,el)=>sum+el.getBoundingClientRect().height,0);
 const next=table&&rowHeight>0?Math.ceil(chrome+rowHeight+48):1320;
 if(next!==height){height=next;send('streamlit:setFrameHeight',{height:next})}
}
const observer=new ResizeObserver(()=>requestAnimationFrame(fit));
observer.observe(document.getElementById('root')!);
new MutationObserver(()=>requestAnimationFrame(fit)).observe(document.getElementById('root')!,{childList:true,subtree:true,characterData:true});
window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='streamlit:render')return;const args=e.data.args as Args;setRole(args.role,args.permissions);acceptResponse(args.response);root.render(<Workspace key={args.storageKey} args={args}/>);requestAnimationFrame(fit)});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){const btn=document.querySelector<HTMLButtonElement>('.row-detail .secondary');btn?.click()}});
window.addEventListener('resize',fit);
send('streamlit:componentReady',{apiVersion:1});
