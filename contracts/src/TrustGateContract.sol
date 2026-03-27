// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

/// @title TrustGateContract
/// @notice DeFi pool access gating by minimum trust score. Any protocol on
///         Tron can use this to block untrusted agents from trading/lending.
/// @dev References TronTrustOracle for score lookups. Pool owner controls
///      the threshold and can whitelist specific addresses.

interface ITronTrustOracle {
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrusted);
    function isTrusted(address _agent, uint8 _minScore) external view returns (bool);
}

contract TrustGateContract {

    // ── Custom Errors ──
    error NotPoolOwner();
    error ScoreOutOfRange(uint8 score);
    error ZeroAddress();

    // ── State ──
    ITronTrustOracle public oracle;
    address public poolOwner;
    uint8 public minScore;
    mapping(address => bool) public exempted;

    // ── Events ──
    event AccessGranted(address indexed agent, uint8 score);
    event AccessDenied(address indexed agent, uint8 score);
    event MinScoreUpdated(uint8 oldScore, uint8 newScore);
    event ExemptionUpdated(address indexed agent, bool exempt);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);

    // ── Modifiers ──
    modifier onlyPoolOwner() {
        if (msg.sender != poolOwner) revert NotPoolOwner();
        _;
    }

    /// @param _oracle TronTrustOracle address
    /// @param _minScore Minimum trust score for pool access (0-100)
    constructor(address _oracle, uint8 _minScore) {
        oracle = ITronTrustOracle(_oracle);
        poolOwner = msg.sender;
        minScore = _minScore;
    }

    /// @notice Update the minimum trust score for access
    function setMinScore(uint8 _minScore) external onlyPoolOwner {
        if (_minScore > 100) revert ScoreOutOfRange(_minScore);
        uint8 old = minScore;
        minScore = _minScore;
        emit MinScoreUpdated(old, _minScore);
    }

    /// @notice Whitelist or remove an agent from exemption list
    function exempt(address _agent, bool _exempt) external onlyPoolOwner {
        exempted[_agent] = _exempt;
        emit ExemptionUpdated(_agent, _exempt);
    }

    /// @notice Update oracle reference
    function setOracle(address _oracle) external onlyPoolOwner {
        if (_oracle == address(0)) revert ZeroAddress();
        address old = address(oracle);
        oracle = ITronTrustOracle(_oracle);
        emit OracleUpdated(old, _oracle);
    }

    /// @notice Transfer pool ownership
    function transferPoolOwnership(address _newOwner) external onlyPoolOwner {
        if (_newOwner == address(0)) revert ZeroAddress();
        poolOwner = _newOwner;
    }

    /// @notice Check if an agent has sufficient trust to access the pool
    /// @param _agent Address to check
    /// @return True if access granted
    function checkAccess(address _agent) external returns (bool) {
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

    /// @notice View-only access check (no events, no gas for state changes)
    function checkAccessView(address _agent) external view returns (bool allowed, uint8 agentScore) {
        if (exempted[_agent]) {
            (uint8 s,,) = oracle.getTrust(_agent);
            return (true, s);
        }
        (uint8 s,, bool trusted) = oracle.getTrust(_agent);
        return (s >= minScore && trusted, s);
    }
}
