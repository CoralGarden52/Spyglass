import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'framer-motion';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { AppShell } from './layouts/AppShell';
import { Workbench } from './pages/Workbench';
import './styles/index.css';

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });
const router = createBrowserRouter([
  { path: '/', Component: AppShell, children: [{ index: true, Component: Workbench }] },
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
