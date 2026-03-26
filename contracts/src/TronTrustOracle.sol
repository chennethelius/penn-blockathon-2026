// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract TronTrustOracle {
    // --- Roles ---
    address public owner;
    address public operator;

    // --- Structs ---
    struct TrustScore {
        uint8 score;       // 0-100
        uint8 verdict;     // 0=unknown, 1=trusted, 2=proceed, 3=caution, 4=avoid
        uint256 lastUpdated;
        bool isBlacklisted;
        string blacklistReason;
    }

    struct AgentProfile {
        string agentType;
        uint256 registeredAt;
        uint256 totalJobs;
        uint256 completedJobs;
        uint256 totalVolumeUsdt;  // in 6-decimal USDT units
        bool exists;
    }

    struct Attestation {
        address subject;
        uint8 score;
        string evidenceCid;
        uint256 createdAt;
        address attestor;
    }

    // --- Storage ---
    mapping(address => TrustScore) public trustScores;
    mapping(address => AgentProfile) public agentProfiles;
    mapping(bytes32 => Attestation) public attestations;

    uint256 public totalAgents;
    uint256 public totalAttestations;

    // --- Events ---
    event ScoreUpdated(address indexed agent, uint8 score, uint8 verdict, uint256 timestamp);
    event AgentRegistered(address indexed agent, string agentType, uint256 timestamp);
    event Blacklisted(address indexed agent, string reason, uint256 timestamp);
    event AttestationCreated(bytes32 indexed attestationId, address indexed subject, uint8 score, string evidenceCid);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    event OwnerTransferred(address indexed oldOwner, address indexed newOwner);

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "TronTrustOracle: caller is not owner");
        _;
    }

    modifier onlyOperator() {
        require(msg.sender == operator, "TronTrustOracle: caller is not operator");
        _;
    }

    // --- Constructor ---
    constructor(address _operator) {
        owner = msg.sender;
        operator = _operator;
    }

    // --- Owner Functions ---
    function setOperator(address _operator) external onlyOwner {
        address old = operator;
        operator = _operator;
        emit OperatorUpdated(old, _operator);
    }

    function transferOwnership(address _newOwner) external onlyOwner {
        require(_newOwner != address(0), "TronTrustOracle: zero address");
        address old = owner;
        owner = _newOwner;
        emit OwnerTransferred(old, _newOwner);
    }

    // --- Operator Functions ---
    function registerAgent(address _agent, string calldata _agentType) external onlyOperator {
        require(!agentProfiles[_agent].exists, "TronTrustOracle: agent already registered");

        agentProfiles[_agent] = AgentProfile({
            agentType: _agentType,
            registeredAt: block.timestamp,
            totalJobs: 0,
            completedJobs: 0,
            totalVolumeUsdt: 0,
            exists: true
        });

        // Initialize trust score at 50 (neutral)
        trustScores[_agent] = TrustScore({
            score: 50,
            verdict: 0,
            lastUpdated: block.timestamp,
            isBlacklisted: false,
            blacklistReason: ""
        });

        totalAgents++;
        emit AgentRegistered(_agent, _agentType, block.timestamp);
        emit ScoreUpdated(_agent, 50, 0, block.timestamp);
    }

    function updateScore(address _agent, uint8 _score, uint8 _verdict) external onlyOperator {
        require(_score <= 100, "TronTrustOracle: score must be 0-100");
        require(_verdict <= 4, "TronTrustOracle: invalid verdict");
        require(!trustScores[_agent].isBlacklisted, "TronTrustOracle: agent is blacklisted");

        trustScores[_agent].score = _score;
        trustScores[_agent].verdict = _verdict;
        trustScores[_agent].lastUpdated = block.timestamp;

        emit ScoreUpdated(_agent, _score, _verdict, block.timestamp);
    }

    function batchUpdateScores(
        address[] calldata _agents,
        uint8[] calldata _scores,
        uint8[] calldata _verdicts
    ) external onlyOperator {
        require(
            _agents.length == _scores.length && _scores.length == _verdicts.length,
            "TronTrustOracle: array length mismatch"
        );

        for (uint256 i = 0; i < _agents.length; i++) {
            if (!trustScores[_agents[i]].isBlacklisted && _scores[i] <= 100 && _verdicts[i] <= 4) {
                trustScores[_agents[i]].score = _scores[i];
                trustScores[_agents[i]].verdict = _verdicts[i];
                trustScores[_agents[i]].lastUpdated = block.timestamp;
                emit ScoreUpdated(_agents[i], _scores[i], _verdicts[i], block.timestamp);
            }
        }
    }

    function blacklist(address _agent, string calldata _reason) external onlyOperator {
        trustScores[_agent].score = 0;
        trustScores[_agent].verdict = 4; // avoid
        trustScores[_agent].isBlacklisted = true;
        trustScores[_agent].blacklistReason = _reason;
        trustScores[_agent].lastUpdated = block.timestamp;

        emit Blacklisted(_agent, _reason, block.timestamp);
        emit ScoreUpdated(_agent, 0, 4, block.timestamp);
    }

    function updateAgentStats(
        address _agent,
        uint256 _totalJobs,
        uint256 _completedJobs,
        uint256 _totalVolumeUsdt
    ) external onlyOperator {
        require(agentProfiles[_agent].exists, "TronTrustOracle: agent not registered");
        agentProfiles[_agent].totalJobs = _totalJobs;
        agentProfiles[_agent].completedJobs = _completedJobs;
        agentProfiles[_agent].totalVolumeUsdt = _totalVolumeUsdt;
    }

    function createAttestation(
        address _subject,
        uint8 _score,
        string calldata _evidenceCid
    ) external onlyOperator returns (bytes32) {
        require(_score <= 100, "TronTrustOracle: score must be 0-100");

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

        totalAttestations++;
        emit AttestationCreated(attestationId, _subject, _score, _evidenceCid);
        return attestationId;
    }

    // --- Public View Functions ---
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrustedBool) {
        TrustScore memory ts = trustScores[_agent];
        return (ts.score, ts.verdict, ts.score >= 60 && !ts.isBlacklisted);
    }

    function isTrusted(address _agent, uint8 _minScore) external view returns (bool) {
        TrustScore memory ts = trustScores[_agent];
        return ts.score >= _minScore && !ts.isBlacklisted;
    }

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
