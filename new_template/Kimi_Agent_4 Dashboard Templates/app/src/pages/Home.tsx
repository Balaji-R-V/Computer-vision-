import { useEffect } from "react";
import Header from "@/components/Header";
import Ticker from "@/components/Ticker";
import ProfileSwitcher from "@/components/ProfileSwitcher";
import AiBrief from "@/components/AiBrief";
import CameraWall from "@/components/CameraWall";
import FloorPlan from "@/components/FloorPlan";
import AlertFeed from "@/components/AlertFeed";
import Analytics from "@/sections/Analytics";
import { useSimulation } from "@/hooks/useSimulation";

export default function Home() {
  const { world, setMode, setTemplate, ackAlert, ackAll, greetVip } = useSimulation(1000);

  useEffect(() => {
    document.title = `Aegis — ${world.template.venue}`;
  }, [world.template.id]);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg)" }}>
      <Header world={world} onMode={setMode} />
      <Ticker world={world} />
      <ProfileSwitcher world={world} onSwitch={setTemplate} />
      <AiBrief world={world} onAckAll={ackAll} />

      {/* mission-control grid */}
      <main className="px-4 py-3 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-[400px_minmax(0,1fr)_370px] gap-3 xl:h-[600px]">
        <div className="h-[480px] xl:h-full min-h-0">
          <CameraWall world={world} />
        </div>
        <div className="h-[480px] xl:h-full min-h-0">
          <FloorPlan world={world} />
        </div>
        <div className="h-[480px] lg:col-span-2 xl:col-span-1 xl:h-full min-h-0">
          <AlertFeed world={world} onAck={ackAlert} onAckAll={ackAll} />
        </div>
      </main>

      <Analytics world={world} onGreet={greetVip} />

      <footer className="px-4 pb-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[8.5px] tracking-[0.12em]" style={{ color: "#2e3d5c" }}>
          <span>AEGIS·OS v3.2 — PROFILE “{world.template.tab}” · {world.template.venue.toUpperCase()}</span>
          <span>·</span>
          <span>SILENT-ALERT POLICY: ALL EVENTS ROUTE TO DEVICES, NO FLOOR AUDIBLE ALARM</span>
          <span>·</span>
          <span>DEMO ENVIRONMENT — ALL FEEDS, IDENTITIES AND EVENTS ARE SIMULATED IN-BROWSER</span>
        </div>
      </footer>
    </div>
  );
}
