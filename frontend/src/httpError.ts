export async function httpError(response:Response):Promise<Error>{
 const raw=await response.text();
 try{const data=JSON.parse(raw);const detail=data.detail??data.error?.message;if(typeof detail==='string')return new Error(detail);if(Array.isArray(detail))return new Error(detail.map(e=>e.msg||'Dữ liệu không hợp lệ').join('; '));}catch{}
 return new Error(raw||`HTTP ${response.status}`);
}
