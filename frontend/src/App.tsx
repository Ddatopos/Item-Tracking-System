import React, { useState } from "react";
import OverviewPage from "./components/OverviewPage";
import ItemTracking from "./components/ItemTracking";
import EventHistory from "./components/EventHistory";
import SettingsPage from "./components/SettingsPage";
import type { AppTab } from "./api/types";

const TABS: { key: AppTab; label: string }[] = [
  { key: "overview", label: "总览" },
  { key: "history", label: "历史" },
  { key: "settings", label: "设置" },
];

function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("overview");

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-top">
          <div className="logo">家庭寻物系统</div>
          <span className="version-tag">V1.0</span>
        </div>
        <nav className="nav-tabs" aria-label="主导航">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`nav-tab ${activeTab === tab.key ? "nav-tab-active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
              aria-current={activeTab === tab.key ? "page" : undefined}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">
        {activeTab === "overview" && <OverviewPage />}
        {activeTab === "history" && (
          <div className="history-page">
            <EventHistory />
            <ItemTracking />
          </div>
        )}
        {activeTab === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}

export default App;