import Foundation
import HealthKit

/// Session d'entraînement HealthKit : garde l'app active écran baissé,
/// lit la fréquence cardiaque et enregistre la séance dans Santé.
@MainActor
final class WorkoutManager: NSObject, ObservableObject {
    let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?

    @Published var heartRate: Double = 0
    @Published var activeEnergy: Double = 0
    @Published var isActive = false

    func requestAuthorization() async {
        guard HKHealthStore.isHealthDataAvailable() else { return }
        let share: Set<HKSampleType> = [HKObjectType.workoutType()]
        let read: Set<HKObjectType> = [
            HKQuantityType(.heartRate),
            HKQuantityType(.activeEnergyBurned),
            HKQuantityType(.distanceWalkingRunning)
        ]
        try? await healthStore.requestAuthorization(toShare: share, read: read)
    }

    func start(activity: HKWorkoutActivityType) async {
        guard !isActive else { return }
        let config = HKWorkoutConfiguration()
        config.activityType = activity
        config.locationType = activity == .running ? .outdoor : .indoor
        do {
            let s = try HKWorkoutSession(healthStore: healthStore, configuration: config)
            let b = s.associatedWorkoutBuilder()
            b.dataSource = HKLiveWorkoutDataSource(healthStore: healthStore, workoutConfiguration: config)
            s.delegate = self
            b.delegate = self
            session = s
            builder = b
            heartRate = 0
            activeEnergy = 0
            let startDate = Date()
            s.startActivity(with: startDate)
            try await b.beginCollection(at: startDate)
            isActive = true
        } catch {
            print("Workout start error: \(error)")
        }
    }

    func pause() { session?.pause() }
    func resume() { session?.resume() }

    func end() async {
        guard let s = session, let b = builder else { return }
        s.end()
        do {
            try await b.endCollection(at: Date())
            _ = try await b.finishWorkout()
        } catch {
            print("Workout end error: \(error)")
        }
        session = nil
        builder = nil
        isActive = false
    }
}

extension WorkoutManager: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession,
                                    didChangeTo toState: HKWorkoutSessionState,
                                    from fromState: HKWorkoutSessionState,
                                    date: Date) {}

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {
        print("Workout session failed: \(error)")
    }
}

extension WorkoutManager: HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}

    nonisolated func workoutBuilder(_ workoutBuilder: HKLiveWorkoutBuilder,
                                    didCollectDataOf collectedTypes: Set<HKSampleType>) {
        let hrType = HKQuantityType(.heartRate)
        let energyType = HKQuantityType(.activeEnergyBurned)
        let bpm = HKUnit.count().unitDivided(by: .minute())
        let hr: Double? = collectedTypes.contains(hrType)
            ? workoutBuilder.statistics(for: hrType)?.mostRecentQuantity()?.doubleValue(for: bpm)
            : nil
        let kcal: Double? = collectedTypes.contains(energyType)
            ? workoutBuilder.statistics(for: energyType)?.sumQuantity()?.doubleValue(for: .kilocalorie())
            : nil
        Task { @MainActor in
            if let hr { self.heartRate = hr }
            if let kcal { self.activeEnergy = kcal }
        }
    }
}
