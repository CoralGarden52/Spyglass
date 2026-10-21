import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router';
import { MessageSquare, Plus } from 'lucide-react';
import { createThread, listThreads } from '../../services/runs';

export function ProjectThreads({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ['project-threads', projectId],
    queryFn: () => listThreads(projectId),
    retry: false,
  });
  const key = useRef(crypto.randomUUID());
  const title = useRef(`研究会话 · ${new Date().toLocaleString('zh-CN')}`);
  const client = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: () => createThread(projectId, title.current, key.current),
    onSuccess: ({ data }) => {
      void client.invalidateQueries({ queryKey: ['project-threads', projectId] });
      navigate(`/threads/${data.id}`);
    },
  });
  return (
    <section className="project-threads">
      <div className="section-heading">
        <div className="section-title">
          <MessageSquare size={21} />
          <h2>研究会话</h2>
        </div>
        <button className="soft-button" disabled={create.isPending} onClick={() => create.mutate()}>
          <Plus size={16} />
          {create.isPending ? '正在创建…' : '新建研究会话'}
        </button>
      </div>
      {create.error && (
        <p className="form-error" role="alert">
          {create.error.message}。重试将使用同一幂等请求。
        </p>
      )}
      {query.isPending ? (
        <p role="status">正在读取会话…</p>
      ) : query.error ? (
        <p className="form-error" role="alert">
          {query.error.message}
          <button className="text-button" onClick={() => void query.refetch()}>
            重试会话列表
          </button>
        </p>
      ) : query.data?.data.length ? (
        <div className="thread-list">
          {query.data.data.map((thread) => (
            <Link key={thread.id} to={`/threads/${thread.id}`}>
              <MessageSquare size={18} />
              <div>
                <h3>{thread.title}</h3>
                <p className="muted">{new Date(thread.created_at).toLocaleString('zh-CN')}</p>
              </div>
              <span>打开会话 →</span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="muted">尚无研究会话。创建后可提交真实研究任务。</p>
      )}
    </section>
  );
}
