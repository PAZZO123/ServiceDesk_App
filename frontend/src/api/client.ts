import {tokens} from "./tokens"
import type { TokenPair } from "./types"
export const API ="/api/v1"


export class ApiError extends Error {
    readonly status:number;
    readonly code:string;
    readonly details:unknown;

    constructor (status:number, code:string, message:string, details?:unknown)
    {
        super(message)
        this.name="ApiError";
        this.status=status;
        this.code=code;
        this.details=details;

    }
}

type ErrorEnvelope={
    error?:{code?:string; message?:string; details?:unknown};
};

async function toApiError(res:Response): Promise<ApiError>{
    let body:ErrorEnvelope |null=null;
    try{
        body=(await res.json()) as ErrorEnvelope;
    }
    catch{
        //Something like vite error
    }
    const err=body?.error;
    return new ApiError(
        res.status,
        err?.code??`http_${res.status}`,
        err?.message??(res.statusText || "Request Failed."),
        err?.details,
    )
}

let sessionExpiredhandler:(()=>void)|null=null;
export function onSessionExpired(handler:()=>void):void{
    sessionExpiredhandler=handler
}


let refreshing: Promise<boolean> | null =null;

function refreshOnce(): Promise<boolean> {
  if (refreshing === null) {
    refreshing = doRefresh().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

async function doRefresh(): Promise<boolean> {
  const refreshToken = tokens.getRefresh();
  if (refreshToken === null) {
    return false;
  }

 const res = await fetch(`${API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    tokens.clear();
    return false;
  }

  tokens.set((await res.json()) as TokenPair);
  return true;
}

type Options = Omit<RequestInit, "body"> & {
  json?: unknown; // sent as JSON
  body?: BodyInit; // FormData (uploads), URLSearchParams (login)
  auth?: boolean; // false for login
};

// Returns the raw Response - used directly for file downloads.
export async function apiRaw(path: string, options: Options = {}): Promise<Response> {
  const { json, body, auth = true, headers, ...rest } = options;

  // A function, because the retry after a refresh must use the NEW token.
  const build = (): RequestInit => {
    const h = new Headers(headers);
    if (json !== undefined) {
      h.set("Content-Type", "application/json");
    }
    const access = tokens.getAccess();
    if (auth && access !== null) {
      h.set("Authorization", `Bearer ${access}`);
    }
    return { ...rest, headers: h, body: json !== undefined ? JSON.stringify(json) : body };
  };

  let res = await fetch(`${API}${path}`, build());

  if (res.status === 401 && auth) {
    if (await refreshOnce()) {
      res = await fetch(`${API}${path}`, build()); // retry exactly once
    } else {
      sessionExpiredhandler?.();
    }
  }

  if (!res.ok) {
    throw await toApiError(res);
  }
  return res;
}

export async function api<T>(path:string, options?:Options): Promise<T> {
    const res=await apiRaw(path, options)
    if(res.status === 204){
        return undefined as T;
    }
    return (await res.json())as T;
}