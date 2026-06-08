import { useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import type { BroadcastEvent } from "../types";
import { supabase } from "../lib/supabase";

export function useMatchChannel(
  roomId: string | null,
  onEvent: (event: BroadcastEvent, payload: unknown) => void,
) {
  const channelRef = useRef<RealtimeChannel | null>(null);
  const eventHandlerRef = useRef(onEvent);
  eventHandlerRef.current = onEvent;

  useEffect(() => {
    const client = supabase;
    if (!client || !roomId) return;

    const channel = client
      .channel(`match:${roomId}`)
      .on("broadcast", { event: "*" }, ({ event, payload }) => {
        eventHandlerRef.current(event as BroadcastEvent, payload);
      })
      .subscribe();

    channelRef.current = channel;
    return () => {
      channelRef.current = null;
      void client.removeChannel(channel);
    };
  }, [roomId]);

  return {
    send: (event: BroadcastEvent, payload: unknown) => {
      void channelRef.current?.send({ type: "broadcast", event, payload });
    },
  };
}
