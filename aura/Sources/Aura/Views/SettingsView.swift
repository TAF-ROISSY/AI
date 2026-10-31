import SwiftUI
import AppKit

struct SettingsView: View {
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var health: HealthCenter
    @EnvironmentObject var selfUpdate: SelfUpdater
    @AppStorage("aura.update.auto") private var autoUpdate = false
    @AppStorage("aura.menuBarEnabled") private var menuBarEnabled = true
    @AppStorage("aura.autoScanVolumes") private var autoScanVolumes = true
    @AppStorage("aura.alerts.enabled") private var alertsEnabled = true
    @AppStorage("aura.alerts.diskPercent") private var diskThreshold = 10.0
    @AppStorage("aura.alerts.temp") private var tempThreshold = 95.0
    @AppStorage("aura.alerts.cpuHog") private var cpuHogThreshold = 85.0
    @Etat private var exclusions: [String] = []
    @Etat private var exclusionSelection: String? = nil

    var body: some View {
        TabView {
            Form {
                Section("Aura") {
                    Toggle("Lancer Aura à l'ouverture de session", isOn: Binding(
                        get: { health.launchAtLogin }, set: { health.launchAtLogin = $0 }))
                    Toggle("Afficher Aura dans la barre des menus (au prochain lancement)", isOn: $menuBarEnabled)
                    Toggle("Analyser chaque nouveau support branché", isOn: $autoScanVolumes)
                }
                Section("Accès") {
                    LabeledContent("Accès complet au disque") {
                        HStack {
                            Text(FS.hasFullDiskAccess ? "Accordé" : "Non accordé")
                                .foregroundStyle(FS.hasFullDiskAccess ? AuraTheme.green : AuraTheme.amber)
                            Button("Réglages…") { FS.openFullDiskAccessSettings() }
                        }
                    }
                }
                Section("Statistiques") {
                    LabeledContent("Espace libéré depuis l'installation") { Text(Fmt.bytes(Int64(cleanup.totalFreed))) }
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Général", systemImage: "gearshape") }

            Form {
                Section("Nettoyage automatique") {
                    Picker("Fréquence", selection: Binding(get: { health.schedule }, set: { health.schedule = $0 })) {
                        ForEach(CleanSchedule.allCases) { Text($0.rawValue).tag($0) }
                    }
                    Text("Ne supprime que ce qui se recrée tout seul : caches, journaux, navigateurs, Xcode, caches de développement. Jamais tes fichiers.")
                        .font(.auraCaption).foregroundStyle(.secondary)
                    if let next = health.nextAutoClean {
                        LabeledContent("Prochain passage") { Text(next.formatted(date: .abbreviated, time: .shortened)) }
                    }
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Planification", systemImage: "calendar.badge.clock") }

            Form {
                Section("Alertes de santé") {
                    Toggle("Me prévenir quand quelque chose cloche", isOn: $alertsEnabled)
                    LabeledContent("Disque presque plein sous") {
                        Stepper("\(Int(diskThreshold)) % libres", value: $diskThreshold, in: 3...30)
                    }
                    LabeledContent("Température critique") {
                        Stepper("\(Int(tempThreshold)) °C", value: $tempThreshold, in: 70...110, step: 5)
                    }
                    LabeledContent("App trop gourmande au-delà de") {
                        Stepper("\(Int(cpuHogThreshold)) % CPU", value: $cpuHogThreshold, in: 50...200, step: 10)
                    }
                }
                if !health.history.isEmpty {
                    Section("Dernières alertes") {
                        ForEach(Array(health.history.prefix(10).enumerated()), id: \.offset) { pair in
                            HStack {
                                Image(systemName: pair.element.1.icon).foregroundStyle(pair.element.1.color)
                                Text(pair.element.1.title)
                                Spacer()
                                Text(Fmt.relativeDate(pair.element.0)).font(.auraCaption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Alertes", systemImage: "bell.badge") }

            Form {
                Section("Mises à jour d'Aura") {
                    LabeledContent("Version installée") { Text(selfUpdate.currentVersion) }
                    Toggle("Installer automatiquement les nouvelles versions", isOn: $autoUpdate)
                    HStack {
                        Button(selfUpdate.isChecking ? "Vérification…" : "Rechercher maintenant") {
                            Task { await selfUpdate.check(silent: false) }
                        }
                        .disabled(selfUpdate.isChecking)
                        if selfUpdate.available != nil {
                            Button("Installer \(selfUpdate.available?.version ?? "")") { Task { await selfUpdate.install() } }
                                .buttonStyle(AuraButton(.primary))
                        }
                    }
                    if !selfUpdate.lastResult.isEmpty {
                        Text(selfUpdate.lastResult).font(.auraCaption).foregroundStyle(.secondary)
                    }
                    Text("Aura vérifie au démarrage puis toutes les 6 heures sur github.com/\(SelfUpdater.repo).")
                        .font(.auraCaption).foregroundStyle(.secondary)
                }
            }
            .formStyle(.grouped)
            .tabItem { Label("Mises à jour", systemImage: "arrow.down.app") }

            VStack(alignment: .leading, spacing: 10) {
                Text("Dossiers jamais touchés par le nettoyage").font(.auraHeadline)
                List(exclusions, id: \.self, selection: $exclusionSelection) { path in
                    HStack {
                        Image(systemName: "folder")
                        Text(path).lineLimit(1).truncationMode(.middle)
                    }
                }
                HStack {
                    Button("Ajouter un dossier…") {
                        if let u = pickFolder() {
                            exclusions.append(u.path)
                            cleanup.exclusions = exclusions
                        }
                    }
                    Button("Retirer") {
                        exclusions.removeAll { $0 == exclusionSelection }
                        cleanup.exclusions = exclusions
                    }
                    .disabled(exclusionSelection == nil)
                }
            }
            .padding()
            .tabItem { Label("Exclusions", systemImage: "hand.raised") }
        }
        .frame(width: 560, height: 420)
        .onAppear { exclusions = cleanup.exclusions }
    }
}
