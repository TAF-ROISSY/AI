import SwiftUI
import AppKit

struct MenuBarView: View {
    @EnvironmentObject var monitor: SystemMonitor
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var volumes: VolumeManager
    @EnvironmentObject var awake: KeepAwake
    @EnvironmentObject var activity: AppActivityMonitor
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "sparkles").foregroundStyle(AuraTheme.accent)
                Text("Aura").font(.auraHeadline)
                Spacer()
                Text("Santé \(monitor.healthScore)/100")
                    .font(.auraCaption.weight(.semibold))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(AuraTheme.scoreColor(monitor.healthScore).opacity(0.25), in: Capsule())
            }

            HStack(spacing: 14) {
                RingGauge(value: monitor.cpuUsage, label: Fmt.percent(monitor.cpuUsage), caption: "CPU",
                          color: AuraTheme.loadColor(monitor.cpuUsage), size: 70, lineWidth: 7)
                RingGauge(value: monitor.memPressure, label: Fmt.percent(monitor.memPressure), caption: "RAM",
                          color: AuraTheme.loadColor(monitor.memPressure), size: 70, lineWidth: 7)
                RingGauge(value: monitor.diskUsedRatio, label: Fmt.percent(monitor.diskUsedRatio), caption: "Disque",
                          color: AuraTheme.loadColor(monitor.diskUsedRatio), size: 70, lineWidth: 7)
            }

            VStack(spacing: 6) {
                row("arrow.down", "Réception", Fmt.rate(monitor.netIn))
                row("arrow.up", "Envoi", Fmt.rate(monitor.netOut))
                row("internaldrive", "Espace libre", Fmt.bytes(monitor.diskFree))
                if monitor.battery.present {
                    row(monitor.battery.isCharging ? "battery.100.bolt" : "battery.75", "Batterie",
                        Fmt.percent(monitor.battery.level))
                }
                if let t = monitor.temps.cpu {
                    row("thermometer.medium", "Processeur", String(format: "%.0f °C", t))
                }
            }

            if !volumes.externalVolumes.isEmpty {
                Divider()
                Text("Appareils connectés").font(.auraCaption).foregroundStyle(.secondary)
                ForEach(volumes.externalVolumes) { v in
                    HStack {
                        Image(systemName: v.symbol).foregroundStyle(AuraTheme.legendDim).frame(width: 18)
                        Text(v.name).font(.auraCallout).lineLimit(1)
                        Spacer()
                        Text("\(Fmt.bytes(v.free)) libres").font(.auraCaption).foregroundStyle(.secondary)
                        if v.isEjectable || v.isRemovable || v.isNetwork {
                            Button { volumes.eject(v) } label: { Image(systemName: "eject.fill") }.buttonStyle(.borderless)
                        }
                    }
                }
            }

            Divider()

            HStack {
                Text("Applications les plus gourmandes").font(.auraCaption).foregroundStyle(.secondary)
                Spacer()
                if !activity.idleApps.isEmpty {
                    Button("Fermer \(activity.idleApps.count) inutilisée(s)") { activity.quitIdleApps() }
                        .buttonStyle(.borderless).font(.auraCaption)
                }
            }
            ForEach(activity.apps.filter { !$0.isBackground || $0.isGreedy }.prefix(4)) { a in
                HStack(spacing: 8) {
                    Image(nsImage: a.icon).resizable().frame(width: 18, height: 18)
                    Text(a.name).lineLimit(1).font(.auraCallout)
                    if a.isGreedy { Image(systemName: "flame.fill").font(.auraCaption2).foregroundStyle(AuraTheme.amber) }
                    Spacer()
                    Text(String(format: "%.0f %%", a.cpu)).font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
                    Text(Fmt.bytes(a.memory)).font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
                        .frame(width: 62, alignment: .trailing)
                    if a.canQuit {
                        Button { activity.quit(a) } label: { Image(systemName: "xmark.circle.fill") }
                            .buttonStyle(.borderless).foregroundStyle(.secondary).help("Quitter \(a.name)")
                    }
                }
            }

            Divider()

            HStack {
                Button {
                    Task {
                        await cleanup.scan()
                        await cleanup.clean()
                    }
                } label: {
                    if cleanup.isScanning || cleanup.isCleaning { ProgressView().controlSize(.small) }
                    else { Label("Nettoyage express", systemImage: "wand.and.stars") }
                }
                .buttonStyle(AuraButton(.primary))
                .disabled(cleanup.isScanning || cleanup.isCleaning)
                Button("Libérer la RAM") { monitor.purgeMemory() }
                Spacer()
                Button {
                    if awake.isActive { awake.deactivate() } else { awake.activate(minutes: 60) }
                } label: {
                    Image(systemName: awake.isActive ? "cup.and.saucer.fill" : "cup.and.saucer")
                        .foregroundStyle(awake.isActive ? AuraTheme.amber : .secondary)
                }
                .buttonStyle(.borderless)
                .help(awake.isActive ? "Rester éveillé : actif (cliquer pour arrêter)" : "Rester éveillé pendant 1 heure")
            }
            if cleanup.lastFreed > 0 {
                Text("Dernier nettoyage : \(Fmt.bytes(cleanup.lastFreed)) libérés").font(.auraCaption).foregroundStyle(AuraTheme.green)
            }

            UpdateButton()

            HStack {
                Button("Ouvrir Aura") {
                    NSApp.activate(ignoringOtherApps: true)
                    openWindow(id: "main")
                }
                Spacer()
                Button("Quitter") { NSApp.terminate(nil) }
            }
            .buttonStyle(.borderless)
        }
        .padding(16)
        .frame(width: 340)
        .onAppear { activity.beginLive() }
        .onDisappear { activity.endLive() }
    }

    private func row(_ icon: String, _ label: String, _ value: String) -> some View {
        HStack {
            Image(systemName: icon).frame(width: 18).foregroundStyle(.secondary)
            Text(label).font(.auraCallout)
            Spacer()
            Text(value).font(.auraCallout.monospacedDigit())
        }
    }
}
