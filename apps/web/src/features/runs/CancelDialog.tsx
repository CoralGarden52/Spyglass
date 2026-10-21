import { useEffect, useRef } from 'react';

export function CancelDialog({
  pending,
  error,
  onCancel,
  onClose,
}: {
  pending: boolean;
  error?: string;
  onCancel: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = ref.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="cancel-dialog"
      aria-label="确认取消运行"
      onCancel={(event) => {
        if (pending) event.preventDefault();
        else onClose();
      }}
    >
      <h2>确认取消运行</h2>
      <p>取消将停止这次研究，已保存的消息、事件与产物仍可查看。关闭页面不会取消运行。</p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="dialog-actions">
        <button className="outline-button" autoFocus onClick={onClose} disabled={pending}>
          继续研究
        </button>
        <button className="primary-button" disabled={pending} onClick={onCancel}>
          {pending ? '正在取消…' : '确认取消'}
        </button>
      </div>
    </dialog>
  );
}
