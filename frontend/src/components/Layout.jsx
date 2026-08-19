import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ChevronDown, File, MessageSquare, PanelLeft, PanelLeftClose, Plus, SquarePen, Trash2, User } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useConversations } from "../conversations/ConversationContext";

const NAV = [
  { to: "/chat", label: "Chat", icon: MessageSquare, end: false },
  { to: "/documents", label: "Documents", icon: File, end: true },
];

const ICON = { size: 20, strokeWidth: 1.75 };

const SIDEBAR_KEY = "alder.sidebar_open";

function readSidebarOpen() {
  try {
    const stored = localStorage.getItem(SIDEBAR_KEY);
    if (stored === "0") return false;
    if (stored === "1") return true;
  } catch {
    // ignore
  }
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches) {
    return false;
  }
  return true;
}

function isMobileLayout() {
  return typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches;
}

export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const {
    conversations,
    activeId,
    startNewChat,
    openConversation,
    deleteConversation,
  } = useConversations();
  const [profileOpen, setProfileOpen] = useState(false);
  const [railProfileOpen, setRailProfileOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(readSidebarOpen);
  const [healthModel, setHealthModel] = useState("");
  const profileRef = useRef(null);
  const railProfileRef = useRef(null);

  const isChat = location.pathname.startsWith("/chat");
  const isDocuments = location.pathname.startsWith("/documents");
  const title = isDocuments ? "Documents" : "Chat";
  const username = user?.email || "—";
  const roleLabel = user?.role || "user";
  const initials = String(username)
    .split("@")[0]
    .slice(0, 2)
    .toUpperCase();

  useEffect(() => {
    if (!profileOpen && !railProfileOpen) return undefined;
    function onPointerDown(ev) {
      if (!profileRef.current?.contains(ev.target)) setProfileOpen(false);
      if (!railProfileRef.current?.contains(ev.target)) setRailProfileOpen(false);
    }
    function onKeyDown(ev) {
      if (ev.key === "Escape") {
        setProfileOpen(false);
        setRailProfileOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [profileOpen, railProfileOpen]);

  useEffect(() => {
    setProfileOpen(false);
    setRailProfileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    fetch("/health")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.model) setHealthModel(data.model);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, sidebarOpen ? "1" : "0");
    } catch {
      // ignore
    }
  }, [sidebarOpen]);

  function closeSidebarIfMobile() {
    if (isMobileLayout()) setSidebarOpen(false);
  }

  function toggleSidebar() {
    setSidebarOpen((open) => !open);
  }

  async function onDelete(id) {
    try {
      await deleteConversation(id);
    } catch {
      // list refresh will reflect server state
    }
  }

  return (
    <div className={`app${sidebarOpen ? "" : " sidebar-collapsed"}`}>
      {sidebarOpen ? (
        <button type="button" className="sidebar-backdrop" aria-label="Close sidebar" onClick={toggleSidebar} />
      ) : null}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <button
            type="button"
            className="sidebar-logo-btn"
            onClick={toggleSidebar}
            title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          >
            <span className="brand-name">Alder AI</span>
            <span className="brand-name-short">AI</span>
          </button>
        </div>
        <nav className="sidebar-nav" aria-label="Main">
          <button
            type="button"
            className="nav-item"
            onClick={() => {
              startNewChat();
              closeSidebarIfMobile();
            }}
            title="New chat"
          >
            <SquarePen {...ICON} />
            <span>New chat</span>
          </button>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              onClick={closeSidebarIfMobile}
              title={label}
            >
              <Icon {...ICON} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-chats">
          <div className="sidebar-chats-head">
            <span>Chats</span>
          </div>
          <div className="sidebar-chat-list" role="list">
            {conversations.length === 0 ? (
              <p className="sidebar-chats-empty">No chats yet</p>
            ) : (
              conversations.map((c) => (
                <div
                  key={c.id}
                  className={`sidebar-chat-item${c.id === activeId ? " active" : ""}`}
                >
                  <button
                    type="button"
                    className="sidebar-chat-open"
                    onClick={() => {
                      openConversation(c.id);
                      closeSidebarIfMobile();
                    }}
                    title={c.title}
                  >
                    <span className="sidebar-chat-title">{c.title || "New chat"}</span>
                  </button>
                  <button
                    type="button"
                    className="sidebar-chat-delete"
                    aria-label="Delete chat"
                    title="Delete"
                    onClick={() => onDelete(c.id)}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="sidebar-foot" title={healthModel || "Ollama"}>
          Local · {healthModel || "Ollama"}
        </div>
        <div className="sidebar-rail-profile" ref={railProfileRef}>
          <button
            type="button"
            className="sidebar-rail-avatar"
            onClick={() => setRailProfileOpen((v) => !v)}
            aria-expanded={railProfileOpen}
            aria-label="Account"
            title={username}
          >
            <User {...ICON} />
          </button>
          {railProfileOpen ? (
            <div className="header-profile-menu sidebar-rail-menu">
              <button type="button" onClick={logout}>
                Log out
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      <div className="main">
        <header className="app-header">
          <div className="header-left">
            <button
              type="button"
              className="sidebar-toggle sidebar-toggle-light"
              onClick={toggleSidebar}
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
              title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose size={18} strokeWidth={2} /> : <PanelLeft size={18} strokeWidth={2} />}
            </button>
            <h1 className="header-title">{title}</h1>
            {isChat ? (
              <button type="button" className="header-new-chat" onClick={startNewChat}>
                <Plus size={15} strokeWidth={2.4} />
                New chat
              </button>
            ) : null}
          </div>
          <div className="header-profile-wrap" ref={profileRef}>
            <button
              type="button"
              className="header-profile"
              onClick={() => setProfileOpen((v) => !v)}
              aria-expanded={profileOpen}
            >
              <span className="avatar">{initials}</span>
              <div className="header-profile-text">
                <strong title={username}>{username}</strong>
                <span>{roleLabel}</span>
              </div>
              <ChevronDown size={16} className={`header-chevron${profileOpen ? " open" : ""}`} />
            </button>
            {profileOpen ? (
              <div className="header-profile-menu">
                <button type="button" onClick={logout}>
                  Log out
                </button>
              </div>
            ) : null}
          </div>
        </header>

        <main className={`content${isChat ? " content-chat" : ""}`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
