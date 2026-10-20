import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'framer-motion';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { AppShell } from './layouts/AppShell';
import { Workbench } from './pages/Workbench';
import { AuthPage } from './pages/AuthPage';
import { AccountSettings } from './pages/AccountSettings';
import { ResearchDetail, ResearchProjects } from './pages/ResearchProjects';
import { RequireAuth } from './features/auth/RequireAuth';
import './styles/index.css';

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });
const router = createBrowserRouter([
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/register', element: <AuthPage mode="register" /> },
  {
    Component: RequireAuth,
    children: [
      {
        path: '/',
        Component: AppShell,
        children: [
          { index: true, Component: Workbench },
          { path: 'research', Component: ResearchProjects },
          { path: 'research/:id', Component: ResearchDetail },
          { path: 'settings', Component: AccountSettings },
        ],
      },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="user">
        <RouterProvider router={router} />
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
