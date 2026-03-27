// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

interface ITronTrustOracle {
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrusted);
    function isTrusted(address _agent, uint8 _minScore) external view returns (bool);
}

contract TrustGateContract {
    // --- State ---
    ITronTrustOracle public oracle;
    address public poolOwner;
    uint8 public minScore;
    mapping(address => bool) public exempted;

    // --- Events ---
    event AccessGranted(address indexed agent, uint8 score);
    event AccessDenied(address indexed agent, uint8 score);
    event MinScoreUpdated(uint8 oldScore, uint8 newScore);
    event ExemptionUpdated(address indexed agent, bool exempt);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);

    // --- Modifiers ---
    modifier onlyPoolOwner() {
        require(msg.sender == poolOwner, "TrustGate: not pool owner");
        _;
    }

    // --- Constructor ---
    constructor(address _oracle, uint8 _minScore) {
        oracle = ITronTrustOracle(_oracle);
        poolOwner = msg.sender;
        minScore = _minScore;
    }

    // --- Pool Owner Functions ---
    function setMinScore(uint8 _minScore) external onlyPoolOwner {
        require(_minScore <= 100, "TrustGate: score out of range");
        uint8 old = minScore;
        minScore = _minScore;
        emit MinScoreUpdated(old, _minScore);
    }

    function exempt(address _agent, bool _exempt) external onlyPoolOwner {
        exempted[_agent] = _exempt;
        emit ExemptionUpdated(_agent, _exempt);
    }

    function setOracle(address _oracle) external onlyPoolOwner {
        address old = address(oracle);
        oracle = ITronTrustOracle(_oracle);
        emit OracleUpdated(old, _oracle);
    }

    function transferPoolOwnership(address _newOwner) external onlyPoolOwner {
        require(_newOwner != address(0), "TrustGate: zero address");
        poolOwner = _newOwner;
    }

    // --- Access Check ---
    function checkAccess(address _agent) external returns (bool) {
        // Exempted agents always pass
        if (exempted[_agent]) {
            (uint8 score,,) = oracle.getTrust(_agent);
            emit AccessGranted(_agent, score);
            return true;
        }

        (uint8 score,, bool trusted) = oracle.getTrust(_agent);

        if (score >= minScore && trusted) {
            emit AccessGranted(_agent, score);
            return true;
        } else {
            emit AccessDenied(_agent, score);
            return false;
        }
    }

    // --- View ---
    function checkAccessView(address _agent) external view returns (bool allowed, uint8 score) {
        if (exempted[_agent]) {
            (uint8 s,,) = oracle.getTrust(_agent);
            return (true, s);
        }

        (uint8 s,, bool trusted) = oracle.getTrust(_agent);
        return (s >= minScore && trusted, s);
    }
}
