import Foundation
import IOKit

// API IOHID (non publiques mais stables, utilisées par les moniteurs système open source)
// pour lire les capteurs de température des Mac Apple Silicon.
@_silgen_name("IOHIDEventSystemClientCreate")
private func IOHIDEventSystemClientCreate(_ allocator: CFAllocator?) -> Unmanaged<CFTypeRef>?
@_silgen_name("IOHIDEventSystemClientSetMatching")
private func IOHIDEventSystemClientSetMatching(_ client: CFTypeRef, _ matching: CFDictionary) -> Int32
@_silgen_name("IOHIDEventSystemClientCopyServices")
private func IOHIDEventSystemClientCopyServices(_ client: CFTypeRef) -> Unmanaged<CFArray>?
@_silgen_name("IOHIDServiceClientCopyProperty")
private func IOHIDServiceClientCopyProperty(_ service: CFTypeRef, _ key: CFString) -> Unmanaged<CFTypeRef>?
@_silgen_name("IOHIDServiceClientCopyEvent")
private func IOHIDServiceClientCopyEvent(_ service: CFTypeRef, _ type: Int64, _ options: Int32, _ timestamp: Int64) -> Unmanaged<CFTypeRef>?
@_silgen_name("IOHIDEventGetFloatValue")
private func IOHIDEventGetFloatValue(_ event: CFTypeRef, _ field: Int32) -> Double

struct SensorReading: Identifiable, Hashable {
    let name: String
    let celsius: Double
    var id: String { name }
}

struct TemperatureSummary {
    var cpu: Double?
    var gpu: Double?
    var ssd: Double?
    var battery: Double?
    var all: [SensorReading] = []
    var hottest: Double? { all.map(\.celsius).max() }
}

enum Sensors {
    private static let typeTemperature: Int64 = 15
    private static let fieldTemperature: Int32 = 15 << 16

    static func readTemperatures() -> TemperatureSummary {
        var summary = TemperatureSummary()
        guard let client = IOHIDEventSystemClientCreate(kCFAllocatorDefault)?.takeRetainedValue() else { return summary }
        let matching: [String: Int] = ["PrimaryUsagePage": 0xff00, "PrimaryUsage": 5]
        _ = IOHIDEventSystemClientSetMatching(client, matching as CFDictionary)
        guard let services = IOHIDEventSystemClientCopyServices(client)?.takeRetainedValue() as NSArray? else { return summary }

        var readings: [SensorReading] = []
        for case let service as CFTypeRef in services {
            guard let nameRef = IOHIDServiceClientCopyProperty(service, "Product" as CFString)?.takeRetainedValue(),
                  let name = nameRef as? String,
                  let event = IOHIDServiceClientCopyEvent(service, typeTemperature, 0, 0)?.takeRetainedValue() else { continue }
            let t = IOHIDEventGetFloatValue(event, fieldTemperature)
            if t > 0 && t < 130 { readings.append(SensorReading(name: name, celsius: t)) }
        }
        // Plusieurs capteurs portent le même nom : on garde le plus chaud
        var byName: [String: Double] = [:]
        for r in readings { byName[r.name] = max(byName[r.name] ?? 0, r.celsius) }
        summary.all = byName.map { SensorReading(name: $0.key, celsius: $0.value) }.sorted { $0.celsius > $1.celsius }

        func avg(_ filter: (String) -> Bool) -> Double? {
            let v = readings.filter { filter($0.name.lowercased()) }.map(\.celsius)
            return v.isEmpty ? nil : v.reduce(0, +) / Double(v.count)
        }
        summary.cpu = avg { $0.contains("tdie") || $0.contains("pacc") || $0.contains("eacc") || $0.contains("cpu") }
        summary.gpu = avg { $0.contains("gpu") }
        summary.ssd = avg { $0.contains("nand") || $0.contains("ssd") }
        summary.battery = avg { $0.contains("battery") || $0.contains("gas gauge") }
        return summary
    }
}
