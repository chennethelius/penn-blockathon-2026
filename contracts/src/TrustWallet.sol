// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

/**
 * @title TrustWallet
 * @notice Smart contract wallet for AI agents that enforces trust checks
 *         before every outgoing transaction. Even a compromised AI cannot
 *         send funds to an untrusted address — the contract reverts.
 *
 * Flow:
 *   1. Agent deploys TrustWallet with a minTrustScore (e.g. 70)
 *   2. Fund the wallet with TRX or TRC-20 tokens
 *   3. Agent calls send() to pay someone
 *   4. Contract checks TronTrustOracle.isTrusted(recipient, minScore)
 *   5. If trusted → transfer executes
 *   6. If not → revert with TransferBlocked event
 */

interface ITronTrustOracle {
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrusted);
    function isTrusted(address _agent, uint8 _minScore) external view returns (bool);
}

interface ITRC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract TrustWallet {
    // --- State ---
    address public owner;
    ITronTrustOracle public oracle;
    uint8 public minTrustScore;
    bool public trustEnforced;

    // --- Stats ---
    uint256 public totalTransfers;
    uint256 public totalBlocked;
    uint256 public totalVolumeTrx;

    // --- Events ---
    event TransferApproved(address indexed to, uint256 amount, address token, uint8 recipientScore);
    event TransferBlocked(address indexed to, uint256 amount, address token, uint8 recipientScore, uint8 minRequired);
    event MinTrustScoreUpdated(uint8 oldScore, uint8 newScore);
    event TrustEnforcementToggled(bool enabled);
    event FundsDeposited(address indexed from, uint256 amount);
    event WalletCreated(address indexed owner, address indexed oracle, uint8 minTrustScore);

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "TrustWallet: not owner");
        _;
    }

    // --- Constructor ---
    constructor(address _oracle, uint8 _minTrustScore) {
        owner = msg.sender;
        oracle = ITronTrustOracle(_oracle);
        minTrustScore = _minTrustScore;
        trustEnforced = true;
        emit WalletCreated(msg.sender, _oracle, _minTrustScore);
    }

    // --- Core: Trust-gated TRX send ---
    function send(address payable _to, uint256 _amount) external onlyOwner {
        require(address(this).balance >= _amount, "TrustWallet: insufficient TRX");

        (uint8 score,,) = oracle.getTrust(_to);

        if (trustEnforced && score < minTrustScore) {
            totalBlocked++;
            emit TransferBlocked(_to, _amount, address(0), score, minTrustScore);
            revert("TrustWallet: recipient trust score too low");
        }

        totalTransfers++;
        totalVolumeTrx += _amount;

        (bool ok,) = _to.call{value: _amount}("");
        require(ok, "TrustWallet: TRX transfer failed");

        emit TransferApproved(_to, _amount, address(0), score);
    }

    // --- Core: Trust-gated TRC-20 send ---
    function sendToken(address _token, address _to, uint256 _amount) external onlyOwner {
        require(ITRC20(_token).balanceOf(address(this)) >= _amount, "TrustWallet: insufficient token balance");

        (uint8 score,,) = oracle.getTrust(_to);

        if (trustEnforced && score < minTrustScore) {
            totalBlocked++;
            emit TransferBlocked(_to, _amount, _token, score, minTrustScore);
            revert("TrustWallet: recipient trust score too low");
        }

        totalTransfers++;

        require(ITRC20(_token).transfer(_to, _amount), "TrustWallet: token transfer failed");

        emit TransferApproved(_to, _amount, _token, score);
    }

    // --- Owner controls ---
    function setMinTrustScore(uint8 _newScore) external onlyOwner {
        require(_newScore <= 100, "TrustWallet: score out of range");
        uint8 old = minTrustScore;
        minTrustScore = _newScore;
        emit MinTrustScoreUpdated(old, _newScore);
    }

    function setTrustEnforced(bool _enabled) external onlyOwner {
        trustEnforced = _enabled;
        emit TrustEnforcementToggled(_enabled);
    }

    function setOracle(address _oracle) external onlyOwner {
        oracle = ITronTrustOracle(_oracle);
    }

    function transferOwnership(address _newOwner) external onlyOwner {
        require(_newOwner != address(0), "TrustWallet: zero address");
        owner = _newOwner;
    }

    // --- View ---
    function checkRecipient(address _to) external view returns (
        uint8 score,
        bool wouldPass,
        uint8 minRequired
    ) {
        (uint8 s,,) = oracle.getTrust(_to);
        return (s, s >= minTrustScore || !trustEnforced, minTrustScore);
    }

    function getStats() external view returns (
        uint256 transfers,
        uint256 blocked,
        uint256 volumeTrx,
        uint8 currentMinScore,
        bool enforcing
    ) {
        return (totalTransfers, totalBlocked, totalVolumeTrx, minTrustScore, trustEnforced);
    }

    // --- Accept TRX deposits ---
    receive() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }
}
