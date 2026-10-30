import SwiftUI
import AppKit

struct MenuBarView: View {
    @EnvironmentObject var monitor: SystemMonitor
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var volumes: VolumeManager
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "sparkles").foregroundStyle(AuraTheme.accent)
                Text("Aura").font(.headline)
                Spacer()
                Text("Santé \(monitor.healthScore)/100")
                    .font(.caption.weight(.semibold))
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
                Text("Appareils connectés").font(.caption).foregroundStyle(.secondary)
                ForEach(volumes.externalVolumes) { v in
                    HStack {
                        Image(systemName: v.symbol).foregroundStyle(.cyan).frame(width: 18)
                        Text(v.name).font(.callout).lineLimit(1)
                        Spacer()
                        Text("\(Fmt.bytes(v.free)) libres").font(.caption).foregroundStyle(.secondary)
                        if v.isEjectable || v.isRemovable || v.isNetwork {
                            Button { volumes.eject(v) } label: { Image(systemName: "eject.fill") }.buttonStyle(.borderless)
                        }
                    }
                }
            }

            Divider()

            Text("Plus gourmands").font(.caption).foregroundStyle(.secondary)
            ForEach(Array(monitor.processes.sorted { $0.cpu > $1.cpu }.prefix(4))) { p in
                HStack {
                    Text(p.name).lineLimit(1).font(.callout)
                    Spacer()
                    Text(String(format: "%.0f %%", p.cpu)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
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
                .buttonStyle(.borderedProminent)
                .disabled(cleanup.isScanning || cleanup.isCleaning)
                Button("Libérer la RAM") { monitor.purgeMemory() }
                Spacer()
            }
            if cleanup.lastFreed > 0 {
                Text("Dernier nettoyage : \(Fmt.bytes(cleanup.lastFreed)) libérés").font(.caption).foregroundStyle(.green)
            }

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
        .frame(width: 320)
    }

    private func row(_ icon: String, _ label: String, _ value: String) -> some View {
        HStack {
            Image(systemName: icon).frame(width: 18).foregroundStyle(.secondary)
            Text(label).font(.callout)
            Spacer()
            Text(value).font(.callout.monospacedDigit())
        }
    }
}
