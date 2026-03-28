// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

/// @title TronTrustOracle
/// @notice On-chain trust score oracle for the Tron agent economy.
///         Any smart contract on Tron can call getTrust() to verify an agent's
///         trustworthiness before executing a transaction.
/// @dev Owner/operator separation: cold wallet owner, hot wallet operator.
///      Supports two-step ownership transfer and emergency pause.
contract TronTrustOracle {

    // ── Custom Errors (saves ~200 gas per revert vs require strings) ──
    error NotOwner();
    error NotOperator();
    error NotPendingOwner();
    error ZeroAddress();
    error AgentAlreadyRegistered(address agent);
    error AgentNotRegistered(address agent);
    error AgentBlacklisted(address agent);
    error ScoreOutOfRange(uint8 score);
    error InvalidVerdict(uint8 verdict);
    error ArrayLengthMismatch();
    error BatchTooLarge(uint256 length);
    error ContractPaused();

    // ── Constants ──
    uint8 public constant MAX_SCORE = 100;
    uint8 public constant MAX_VERDICT = 4;
    uint8 public constant INITIAL_SCORE = 50;
    uint256 public constant MAX_BATCH_SIZE = 100;

    // ── Structs ──
    /// @dev INVARIANT: blacklisted agents always have score == 0 and verdict == 4
    struct TrustScore {
        uint8 score;           // 0-100
        uint8 verdict;         // 0=unknown, 1=trusted, 2=reputable, 3=caution, 4=avoid
        uint256 lastUpdated;
        bool isBlacklisted;
        string blacklistReason;
    }

    struct AgentProfile {
        string agentType;
        uint256 registeredAt;
        uint256 totalJobs;
        uint256 completedJobs;
        uint256 totalVolumeUsdt; // 6-decimal USDT units
        bool exists;
    }

    struct Attestation {
        address subject;
        uint8 score;
        string evidenceCid;
        uint256 createdAt;
        address attestor;
    }

    // ── State ──
    address public owner;
    address public pendingOwner;
    address public operator;
    bool public paused;

    mapping(address => TrustScore) public trustScores;
    mapping(address => AgentProfile) public agentProfiles;
    mapping(bytes32 => Attestation) public attestations;

    uint256 public totalAgents;
    uint256 public totalAttestations;

    // ── Events ──
    event ScoreUpdated(address indexed agent, uint8 score, uint8 indexed verdict, uint256 timestamp);
    event AgentRegistered(address indexed agent, string agentType, uint256 timestamp);
    event Blacklisted(address indexed agent, string reason, uint256 timestamp);
    event AttestationCreated(bytes32 indexed attestationId, address indexed subject, uint8 score, string evidenceCid);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    event OwnershipTransferStarted(address indexed currentOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed oldOwner, address indexed newOwner);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ──
    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyOperator() {
        if (msg.sender != operator) revert NotOperator();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert ContractPaused();
        _;
    }

    // ── Constructor ──
    /// @param _operator Hot wallet address that pushes score updates
    constructor(address _operator) {
        if (_operator == address(0)) revert ZeroAddress();
        owner = msg.sender;
        operator = _operator;
    }

    // ══════════════════════════════════════════════
    // Owner Functions
    // ══════════════════════════════════════════════

    /// @notice Start two-step ownership transfer
    /// @param _newOwner Address that must call acceptOwnership()
    function transferOwnership(address _newOwner) external onlyOwner {
        if (_newOwner == address(0)) revert ZeroAddress();
        pendingOwner = _newOwner;
        emit OwnershipTransferStarted(owner, _newOwner);
    }

    /// @notice Complete ownership transfer (must be called by pendingOwner)
    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert NotPendingOwner();
        address old = owner;
        owner = pendingOwner;
        pendingOwner = address(0);
        emit OwnershipTransferred(old, owner);
    }

    /// @notice Update the operator (hot wallet) address
    function setOperator(address _operator) external onlyOwner {
        if (_operator == address(0)) revert ZeroAddress();
        address old = operator;
        operator = _operator;
        emit OperatorUpdated(old, _operator);
    }

    /// @notice Emergency pause — stops all score updates and registrations
    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    /// @notice Resume operations after pause
    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    // ══════════════════════════════════════════════
    // Operator Functions
    // ══════════════════════════════════════════════

    /// @notice Register a new agent with initial trust score of 50
    /// @param _agent Tron address to register
    /// @param _agentType Human-readable type (e.g. "DeFi Bot", "Trading Agent")
    function registerAgent(address _agent, string calldata _agentType) external onlyOperator whenNotPaused {
        if (_agent == address(0)) revert ZeroAddress();
        if (agentProfiles[_agent].exists) revert AgentAlreadyRegistered(_agent);

        agentProfiles[_agent] = AgentProfile({
            agentType: _agentType,
            registeredAt: block.timestamp,
            totalJobs: 0,
            completedJobs: 0,
            totalVolumeUsdt: 0,
            exists: true
        });

        trustScores[_agent] = TrustScore({
            score: INITIAL_SCORE,
            verdict: 0,
            lastUpdated: block.timestamp,
            isBlacklisted: false,
            blacklistReason: ""
        });

        unchecked { totalAgents++; }
        emit AgentRegistered(_agent, _agentType, block.timestamp);
        emit ScoreUpdated(_agent, INITIAL_SCORE, 0, block.timestamp);
    }

    /// @notice Update an agent's trust score and verdict
    /// @param _agent Address to update
    /// @param _score New score (0-100)
    /// @param _verdict 0=unknown, 1=trusted, 2=reputable, 3=caution, 4=avoid
    function updateScore(address _agent, uint8 _score, uint8 _verdict) external onlyOperator whenNotPaused {
        if (_score > MAX_SCORE) revert ScoreOutOfRange(_score);
        if (_verdict > MAX_VERDICT) revert InvalidVerdict(_verdict);
        if (trustScores[_agent].isBlacklisted) revert AgentBlacklisted(_agent);

        trustScores[_agent].score = _score;
        trustScores[_agent].verdict = _verdict;
        trustScores[_agent].lastUpdated = block.timestamp;

        emit ScoreUpdated(_agent, _score, _verdict, block.timestamp);
    }

    /// @notice Batch update scores for gas efficiency
    /// @dev Silently skips invalid entries (blacklisted, out of range)
    /// @param _agents Array of addresses
    /// @param _scores Array of scores (0-100)
    /// @param _verdicts Array of verdicts (0-4)
    function batchUpdateScores(
        address[] calldata _agents,
        uint8[] calldata _scores,
        uint8[] calldata _verdicts
    ) external onlyOperator whenNotPaused {
        if (_agents.length != _scores.length || _scores.length != _verdicts.length)
            revert ArrayLengthMismatch();
        if (_agents.length > MAX_BATCH_SIZE) revert BatchTooLarge(_agents.length);

        for (uint256 i = 0; i < _agents.length;) {
            if (!trustScores[_agents[i]].isBlacklisted &&
                _scores[i] <= MAX_SCORE &&
                _verdicts[i] <= MAX_VERDICT
            ) {
                trustScores[_agents[i]].score = _scores[i];
                trustScores[_agents[i]].verdict = _verdicts[i];
                trustScores[_agents[i]].lastUpdated = block.timestamp;
                emit ScoreUpdated(_agents[i], _scores[i], _verdicts[i], block.timestamp);
            }
            unchecked { i++; }
        }
    }

    /// @notice Blacklist an agent — sets score to 0, verdict to avoid
    /// @param _agent Address to blacklist
    /// @param _reason Human-readable reason (stored on-chain)
    function blacklist(address _agent, string calldata _reason) external onlyOperator whenNotPaused {
        TrustScore storage ts = trustScores[_agent];
        ts.score = 0;
        ts.verdict = 4;
        ts.isBlacklisted = true;
        ts.blacklistReason = _reason;
        ts.lastUpdated = block.timestamp;

        emit Blacklisted(_agent, _reason, block.timestamp);
        emit ScoreUpdated(_agent, 0, 4, block.timestamp);
    }

    /// @notice Update agent job statistics
    function updateAgentStats(
        address _agent,
        uint256 _totalJobs,
        uint256 _completedJobs,
        uint256 _totalVolumeUsdt
    ) external onlyOperator {
        if (!agentProfiles[_agent].exists) revert AgentNotRegistered(_agent);
        AgentProfile storage p = agentProfiles[_agent];
        p.totalJobs = _totalJobs;
        p.completedJobs = _completedJobs;
        p.totalVolumeUsdt = _totalVolumeUsdt;
    }

    /// @notice Create an immutable on-chain attestation with evidence CID
    /// @return attestationId Unique identifier for this attestation
    function createAttestation(
        address _subject,
        uint8 _score,
        string calldata _evidenceCid
    ) external onlyOperator returns (bytes32) {
        if (_score > MAX_SCORE) revert ScoreOutOfRange(_score);

        bytes32 attestationId = keccak256(
            abi.encodePacked(_subject, _score, _evidenceCid, block.timestamp, totalAttestations)
        );

        attestations[attestationId] = Attestation({
            subject: _subject,
            score: _score,
            evidenceCid: _evidenceCid,
            createdAt: block.timestamp,
            attestor: msg.sender
        });

        unchecked { totalAttestations++; }
        emit AttestationCreated(attestationId, _subject, _score, _evidenceCid);
        return attestationId;
    }

    // ══════════════════════════════════════════════
    // Public View Functions
    // ══════════════════════════════════════════════

    /// @notice Get trust score, verdict, and trusted status for an agent
    /// @param _agent Address to query
    /// @return score Trust score 0-100
    /// @return verdict 0=unknown through 4=avoid
    /// @return isTrustedBool True if score >= 60 and not blacklisted
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrustedBool) {
        TrustScore memory ts = trustScores[_agent];
        return (ts.score, ts.verdict, ts.score >= 60 && !ts.isBlacklisted);
    }

    /// @notice Check if an agent meets a minimum trust threshold
    /// @param _agent Address to check
    /// @param _minScore Minimum acceptable score
    /// @return True if agent's score >= _minScore and not blacklisted
    function isTrusted(address _agent, uint8 _minScore) external view returns (bool) {
        TrustScore memory ts = trustScores[_agent];
        return ts.score >= _minScore && !ts.isBlacklisted;
    }

    /// @notice Get full agent profile
    function getAgentProfile(address _agent) external view returns (
        string memory agentType,
        uint256 registeredAt,
        uint256 totalJobs,
        uint256 completedJobs,
        uint256 totalVolumeUsdt,
        bool exists
    ) {
        AgentProfile memory p = agentProfiles[_agent];
        return (p.agentType, p.registeredAt, p.totalJobs, p.completedJobs, p.totalVolumeUsdt, p.exists);
    }

    /// @notice Get attestation details by ID
    function getAttestation(bytes32 _id) external view returns (
        address subject,
        uint8 score,
        string memory evidenceCid,
        uint256 createdAt,
        address attestor
    ) {
        Attestation memory a = attestations[_id];
        return (a.subject, a.score, a.evidenceCid, a.createdAt, a.attestor);
    }
}
