import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl!, supabaseAnonKey!, {
      realtime: {
        params: {
          eventsPerSecond: 10,
        },
      },
    })
  : null;

export async function invokeFunction<T>(
  functionName: string,
  body: Record<string, unknown>,
  method: "POST" | "DELETE" = "POST",
): Promise<T> {
  if (!supabase) {
    throw new Error("Supabase is not configured. Fill VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
  }

  const { data, error } = await supabase.functions.invoke<T>(functionName, {
    method,
    body,
  });

  if (error) {
    throw new Error(error.message);
  }
  if (!data) {
    throw new Error(`No data returned from ${functionName}.`);
  }
  return data;
}
