import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useMatch, useNavigate } from "react-router-dom";
import { api } from "../api/client";

export const CONV_KEY = "alder.conversation_id";

const ConversationContext = createContext(null);

export function ConversationProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const match = useMatch("/chat/:conversationId");
  const routeId = match?.params.conversationId || "";

  const [conversations, setConversations] = useState([]);
  const [draftNonce, setDraftNonce] = useState(0);

  const refreshList = useCallback(async () => {
    try {
      const data = await api("/v1/conversations");
      setConversations(data.conversations || []);
    } catch {
      setConversations([]);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (routeId) sessionStorage.setItem(CONV_KEY, routeId);
  }, [routeId]);

  const startNewChat = useCallback(() => {
    sessionStorage.removeItem(CONV_KEY);
    setDraftNonce((n) => n + 1);
    if (location.pathname !== "/chat") navigate("/chat");
  }, [location.pathname, navigate]);

  const openConversation = useCallback(
    (id) => {
      if (!id) return;
      sessionStorage.setItem(CONV_KEY, id);
      navigate(`/chat/${id}`);
    },
    [navigate],
  );

  const rememberConversation = useCallback(
    (id) => {
      if (!id) return;
      sessionStorage.setItem(CONV_KEY, id);
      refreshList();
      if (routeId !== id) navigate(`/chat/${id}`, { replace: true });
    },
    [navigate, refreshList, routeId],
  );

  const deleteConversation = useCallback(
    async (id) => {
      await api(`/v1/conversations/${id}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (routeId === id || sessionStorage.getItem(CONV_KEY) === id) {
        sessionStorage.removeItem(CONV_KEY);
        setDraftNonce((n) => n + 1);
        navigate("/chat");
      }
    },
    [navigate, routeId],
  );

  const visibleConversations = useMemo(
    () => conversations.filter((c) => (c.message_count || 0) > 0),
    [conversations],
  );

  const activeTitle = visibleConversations.find((c) => c.id === routeId)?.title || "";

  const value = useMemo(
    () => ({
      conversations: visibleConversations,
      activeId: routeId,
      activeTitle,
      draftNonce,
      refreshList,
      startNewChat,
      openConversation,
      rememberConversation,
      deleteConversation,
    }),
    [
      visibleConversations,
      routeId,
      activeTitle,
      draftNonce,
      refreshList,
      startNewChat,
      openConversation,
      rememberConversation,
      deleteConversation,
    ],
  );

  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>;
}

export function useConversations() {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error("useConversations must be used within ConversationProvider");
  return ctx;
}
