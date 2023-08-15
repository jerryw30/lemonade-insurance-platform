import Foundation
import Combine
import AVFoundation

/// ViewModel for claim submission flow
/// Handles video recording, AI analysis, and real-time status updates
class ClaimSubmissionViewModel: ObservableObject {
    
    // MARK: - Published State
    @Published var currentStep: ClaimStep = .incidentDetails
    @Published var claimRequest: ClaimRequest = ClaimRequest()
    @Published var submissionState: SubmissionState = .idle
    @Published var instantApprovalResult: InstantApprovalResult?
    @Published var errorMessage: String?
    
    // MARK: - Dependencies
    private let claimsService: ClaimsServiceProtocol
    private let videoProcessor: VideoProcessingService
    private let fraudDetection: FraudDetectionService
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Constants
    private let maxVideoDuration: TimeInterval = 120 // 2 minutes
    private let maxFileSize: Int64 = 100 * 1024 * 1024 // 100MB
    
    init(claimsService: ClaimsServiceProtocol = ClaimsService(),
         videoProcessor: VideoProcessingService = VideoProcessingService(),
         fraudDetection: FraudDetectionService = FraudDetectionService()) {
        self.claimsService = claimsService
        self.videoProcessor = videoProcessor
        self.fraudDetection = fraudDetection
    }
    
    // MARK: - Public Methods
    
    func submitClaim() {
        guard validateClaim() else { return }
        
        submissionState = .submitting
        
        // Step 1: Upload video evidence asynchronously
        uploadVideoEvidence()
            .flatMap { [weak self] videoUrl -> AnyPublisher<ClaimResponse, Error> in
                guard let self = self else {
                    return Fail(error: ClaimError.unknown).eraseToAnyPublisher()
                }
                self.claimRequest.videoEvidenceUrl = videoUrl
                
                // Step 2: Submit to claims service
                return self.claimsService.submitClaim(self.claimRequest)
            }
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    if case .failure(let error) = completion {
                        self?.handleError(error)
                    }
                },
                receiveValue: { [weak self] response in
                    self?.handleSubmissionResponse(response)
                }
            )
            .store(in: &cancellables)
    }
    
    private func handleSubmissionResponse(_ response: ClaimResponse) {
        switch response.status {
        case .instantApproved:
            submissionState = .approved
            instantApprovalResult = InstantApprovalResult(
                amount: response.payoutAmount,
                processingTime: response.processingTimeMs
            )
            
            // Haptic feedback for success
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            
            // Trigger confetti animation
            NotificationCenter.default.post(name: .showConfetti, object: nil)
            
        case .underReview:
            submissionState = .underReview
            // Schedule push notification for updates
            scheduleStatusUpdates(for: response.claimId)
            
        case .rejected, .flagged:
            submissionState = .rejected
            errorMessage = response.nextSteps
        }
    }
    
    private func uploadVideoEvidence() -> AnyPublisher<String, Error> {
        guard let videoUrl = claimRequest.localVideoUrl else {
            return Just("").setFailureType(to: Error.self).eraseToAnyPublisher()
        }
        
        // Compress video before upload
        return videoProcessor.compressVideo(videoUrl, maxSize: maxFileSize)
            .flatMap { compressedUrl in
                self.videoProcessor.uploadToS3(compressedUrl, bucket: "lemonade-claims-videos")
            }
            .eraseToAnyPublisher()
    }
    
    private func validateClaim() -> Bool {
        // Business logic validation
        guard claimRequest.estimatedAmount > 0 else {
            errorMessage = "Please enter a valid claim amount"
            return false
        }
        
        guard claimRequest.incidentDate < Date() else {
            errorMessage = "Incident date cannot be in the future"
            return false
        }
        
        // Fraud prevention: Check for rapid successive submissions
        if fraudDetection.isSubmittingTooFrequently() {
            errorMessage = "Please wait before submitting another claim"
            return false
        }
        
        return true
    }
}

// MARK: - Supporting Types

enum ClaimStep: CaseIterable {
    case incidentDetails
    case damageAssessment
    case videoEvidence
    case review
    case submission
}

enum SubmissionState {
    case idle
    case uploadingVideo(progress: Double)
    case submitting
    case approved
    case underReview
    case rejected
}

struct InstantApprovalResult {
    let amount: Double
    let processingTime: Int // milliseconds
}
