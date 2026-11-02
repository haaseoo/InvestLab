import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * 브라우저용 Supabase 클라이언트. 공개용(publishable) 키만 쓴다.
 * 로그인 세션은 Supabase JS 기본값대로 브라우저 저장소에 보관되고 자동으로 갱신된다.
 * 데이터는 Supabase에서 직접 읽지 않고 항상 FastAPI를 거친다. 여기서는 인증만 쓴다.
 */
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const authConfigured = Boolean(url && key);

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (typeof window === "undefined" || !url || !key) return null;
  client ??= createClient(url, key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
  return client;
}

/** 만료가 가까우면 Supabase JS가 갱신한 뒤 돌려준다. 로그인하지 않았으면 null. */
export async function getAccessToken(): Promise<string | null> {
  const supabase = getSupabase();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
