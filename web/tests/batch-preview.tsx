/** Local visual fixture: no backend, uploads, or official submissions. */
import { createRoot } from 'react-dom/client';
import ReportFlowModal from '../src/components/ReportFlowModal';
import { ToastProvider } from '../src/components/ui';
import { DEFAULT_APP_CONFIG } from '../src/hooks/useAppConfig';
import '../src/styles/app.css';

createRoot(document.getElementById('root')!).render(
  <ToastProvider>
    <ReportFlowModal
      stage="form"
      config={DEFAULT_APP_CONFIG}
      ocrResults={{
        suspect_ids: ['測試角色甲', '測試角色乙', '測試角色丙'],
        map_name: '弓箭手村',
        media_path: '',
        media_type: 'video',
      }}
      onClose={() => undefined}
      onSubmitReport={() => undefined}
      onUpdateWhitelist={() => undefined}
    />
  </ToastProvider>
);
