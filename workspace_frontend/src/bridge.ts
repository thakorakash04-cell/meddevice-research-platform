let role='viewer',permissions:Record<string,boolean>={},origin='*';
let pending:{id:string;resolve:(value:boolean)=>void}|null=null;
export const isAdmin=()=>role==='admin';
export const canExport=()=>isAdmin()||permissions.download===true;
export const setRole=(value:string,rights:Record<string,boolean>={})=>{role=value;permissions=rights};
export function acceptResponse(response?:{id:string;ok:boolean;error?:string}){if(response&&pending?.id===response.id){if(response.error)alert(response.error);pending.resolve(response.ok);pending=null}}
export function authorizeExport():Promise<boolean>{if(!canExport()||pending)return Promise.resolve(false);return new Promise(resolve=>{const id=crypto.randomUUID();pending={id,resolve};window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value:{id,action:'export'},dataType:'json'},origin);setTimeout(()=>{if(pending?.id===id){pending.resolve(false);pending=null}},30000)})}
