import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { getIdentity, type Identity } from '../../services/auth';
import { useWorkbench } from '../../stores/workbench';

export const identityKey = ['auth', 'me'] as const;
export function resetPrivateState(client: QueryClient) {
  useWorkbench.getState().reset();
  client.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' });
}

export function useIdentity() {
  const client = useQueryClient();
  return useQuery({
    queryKey: identityKey,
    queryFn: async () => {
      const next = await getIdentity();
      const previous = client.getQueryData<Identity | null>(identityKey);
      if (previous?.user.id !== next?.user.id || previous?.tenant.id !== next?.tenant.id) {
        resetPrivateState(client);
      }
      return next;
    },
    staleTime: 0,
    retry: false,
  });
}
