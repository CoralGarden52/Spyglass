import { deriveStages } from './stages';
import type { RunEvent } from '../../services/runs';
import {
  Check,
  FilePenLine,
  FileText,
  Layers3,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
const icons = [Sparkles, Layers3, Search, FileText, Network, FilePenLine, ShieldCheck];
export function StageTimeline({ events }: { events: RunEvent[] }) {
  return (
    <ol className="stage-timeline" aria-label="研究阶段">
      {deriveStages(events).map((stage, index) => {
        const Icon = icons[index];
        return (
          <li key={stage.node} className={`stage-${stage.status}`}>
            <span className="stage-icon">
              <Icon size={19} />
              {stage.status === 'completed' && <Check size={10} className="stage-check" />}
            </span>
            <strong>{stage.label}</strong>
            <small>
              {
                {
                  waiting: '待执行',
                  running: '进行中',
                  completed: '已完成',
                  failed: '失败',
                  cancelled: '已取消',
                }[stage.status]
              }
            </small>
          </li>
        );
      })}
    </ol>
  );
}
