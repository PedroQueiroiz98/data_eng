import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { PageHeader, Tabs } from "@/ui";
import { InfoIcon } from "@/ui/icons";
import { NotificationProviderList } from "@/components/notifications/NotificationProviderList";
import { NotificationDeliveryHistory } from "@/components/notifications/NotificationDeliveryHistory";

export function NotificationsPage() {
  const { user } = useAuthContext();
  const canManage = user?.role === "admin";
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") === "history" ? "history" : "providers");

  return (
    <div>
      <PageHeader
        title="Notificações"
        subtitle="Configure os provedores de envio de notificações do sistema."
      />

      <div className="mb-4 flex gap-3 rounded-lg border border-surface-border bg-surface-variant/50 p-3 text-sm">
        <InfoIcon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p className="text-fg-muted">
          <span className="font-medium text-fg">Configuração global.</span> Os provedores
          aqui são usados pelo sistema para enviar notificações automaticamente (falha de
          jobs, workflows). Quando um evento ocorre, todos os provedores ativos recebem a
          notificação de forma independente.
        </p>
      </div>

      <Tabs
        tabs={[
          { id: "providers", label: "Provedores" },
          { id: "history", label: "Histórico de envios" },
        ]}
        active={tab}
        onChange={setTab}
      />

      <div className="mt-4">
        {tab === "providers" ? (
          <NotificationProviderList canManage={canManage} />
        ) : (
          <NotificationDeliveryHistory
            workflowFilter={params.get("workflow_id") ?? undefined}
          />
        )}
      </div>
    </div>
  );
}
