import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import DataGrid from './data-grid';
import {setRole} from './bridge';
import type {Cell} from './grid-utils';
import './globals.css';
import './workspace.css';
type Args={headers:string[];rows:Cell[][];title:string;role:string;storageKey:string};
function Workspace({args}:{args:Args}){
 const [selected,setSelected]=useState<Cell[]|null>(null);
 return <div className="workspace-table"><div className="paneltitle"><h2>{args.title}</h2><span>Click a value to see its complete row</span></div><DataGrid headers={args.headers} rows={args.rows} storageKey={args.storageKey} filename={args.title} onCell={r=>setSelected(r)}/>{selected&&<div className="row-detail" role="dialog" aria-modal="true" aria-label="Full-window record details"><div className="detailtopbar"><button className="secondary" onClick={()=>setSelected(null)}>← Back to table</button><h2>Record details</h2></div><dl>{args.headers.map((h,i)=><div key={h}><dt>{h}</dt><dd>{String(selected[i]??'—').split(/(https?:\/\/[^\s]+)/g).map((s,j)=>/^https?:\/\//.test(s)?<a key={j} href={s} target="_blank" rel="noreferrer">{s}</a>:s)}</dd></div>)}</dl></div>}</div>
}
const root=createRoot(document.getElementById('root')!);
const send=(type:string,extra:Record<string,unknown>)=>window.parent.postMessage({isStreamlitMessage:true,type,...extra},'*');
let height=0;
function fit(){let next=window.screen.availHeight-150;try{next=window.parent.innerHeight-90}catch{}next=Math.max(420,next);if(next!==height){height=next;send('streamlit:setFrameHeight',{height:next})}}
window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='streamlit:render')return;const args=e.data.args as Args;setRole(args.role);root.render(<Workspace key={args.storageKey} args={args}/>);fit()});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){const btn=document.querySelector<HTMLButtonElement>('.row-detail .secondary');btn?.click()}});
window.addEventListener('resize',fit);
send('streamlit:componentReady',{apiVersion:1});
