import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ConversationProvider } from "./conversations/ConversationContext";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Chat } from "./pages/Chat";
import { Documents } from "./pages/Documents";

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="boot-screen">
        <div className="boot-spinner" />
        <span>Verifying session…</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="boot-screen">
        <div className="boot-spinner" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ConversationProvider>
              <Layout />
            </ConversationProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<Chat />} />
        <Route path="chat/:conversationId" element={<Chat />} />
        <Route path="documents" element={<Documents />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
