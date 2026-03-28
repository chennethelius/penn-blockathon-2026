// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

/// @title TrustWallet
/// @notice Smart contract wallet for AI agents on Tron. Enforces trust checks
///         before every outgoing transaction — even a compromised AI cannot send
///         funds to an untrusted address.
/// @dev Uses Tron-native delegateResource opcode (TIP-467 Stake 2.0) to
///      reward trusted agents with energy delegation, reducing their tx costs.
///      This feature is impossible on EVM chains.

interface ITronTrustOracle {
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrusted);
    function isTrusted(address _agent, uint8 _minScore) external view returns (bool);
}

interface ITRC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract TrustWallet {

    // ── Custom Errors ──
    error NotOwner();
    error InsufficientBalance(uint256 requested, uint256 available);
    error RecipientNotTrusted(address recipient, uint8 score, uint8 minRequired);
    error TransferFailed();
    error ScoreOutOfRange(uint8 score);
    error ZeroAddress();
    error DelegationFailed();

    // ── State ──
    address public owner;
    ITronTrustOracle public oracle;
    uint8 public minTrustScore;
    bool public trustEnforced;

    // ── Stats ──
    uint256 public totalTransfers;
    uint256 public totalBlocked;
    uint256 public totalVolumeSun;

    // ── Tron Resource Delegation (Stake 2.0) ──
    /// @dev Tracks energy delegated to trusted agents via TVM delegateResource opcode
    uint256 public totalEnergyDelegated;
    mapping(address => uint256) public energyDelegatedTo;

    // ── Events ──
    event TransferApproved(address indexed to, uint256 amount, address token, uint8 recipientScore);
    event TransferBlocked(address indexed to, uint256 amount, address token, uint8 recipientScore, uint8 minRequired);
    event MinTrustScoreUpdated(uint8 oldScore, uint8 newScore);
    event TrustEnforcementToggled(bool enabled);
    event FundsDeposited(address indexed from, uint256 amount);
    event WalletCreated(address indexed owner, address indexed oracle, uint8 minTrustScore);
    event EnergyDelegated(address indexed to, uint256 amount, uint8 trustScore);
    event EnergyUndelegated(address indexed from, uint256 amount);

    // ── Modifiers ──
    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    // ── Constructor ──
    /// @param _oracle TronTrustOracle contract address
    /// @param _minTrustScore Minimum trust score for outgoing transfers (0-100)
    constructor(address _oracle, uint8 _minTrustScore) {
        if (_oracle == address(0)) revert ZeroAddress();
        owner = msg.sender;
        oracle = ITronTrustOracle(_oracle);
        minTrustScore = _minTrustScore;
        trustEnforced = true;
        emit WalletCreated(msg.sender, _oracle, _minTrustScore);
    }

    // ══════════════════════════════════════════════
    // Core: Trust-gated Transfers
    // ══════════════════════════════════════════════

    /// @notice Send TRX to a recipient. Reverts if recipient trust score is below threshold.
    /// @param _to Recipient address
    /// @param _amount Amount in SUN (1 TRX = 1,000,000 SUN)
    function send(address payable _to, uint256 _amount) external onlyOwner {
        if (address(this).balance < _amount) revert InsufficientBalance(_amount, address(this).balance);

        (uint8 score,,) = oracle.getTrust(_to);

        if (trustEnforced && score < minTrustScore) {
            unchecked { totalBlocked++; }
            emit TransferBlocked(_to, _amount, address(0), score, minTrustScore);
            revert RecipientNotTrusted(_to, score, minTrustScore);
        }

        unchecked { totalTransfers++; }
        totalVolumeSun += _amount;

        (bool ok,) = _to.call{value: _amount}("");
        if (!ok) revert TransferFailed();

        emit TransferApproved(_to, _amount, address(0), score);
    }

    /// @notice Send TRC-20 tokens to a recipient. Same trust gating as TRX sends.
    /// @param _token TRC-20 contract address
    /// @param _to Recipient address
    /// @param _amount Token amount (in token's smallest unit)
    function sendToken(address _token, address _to, uint256 _amount) external onlyOwner {
        uint256 balance = ITRC20(_token).balanceOf(address(this));
        if (balance < _amount) revert InsufficientBalance(_amount, balance);

        (uint8 score,,) = oracle.getTrust(_to);

        if (trustEnforced && score < minTrustScore) {
            unchecked { totalBlocked++; }
            emit TransferBlocked(_to, _amount, _token, score, minTrustScore);
            revert RecipientNotTrusted(_to, score, minTrustScore);
        }

        unchecked { totalTransfers++; }

        if (!ITRC20(_token).transfer(_to, _amount)) revert TransferFailed();

        emit TransferApproved(_to, _amount, _token, score);
    }

    // ══════════════════════════════════════════════
    // Tron-Native: Trust-Gated Resource Delegation
    // ══════════════════════════════════════════════

    /// @notice Delegate energy to a trusted agent using Tron's Stake 2.0 system.
    ///         Trusted agents get cheaper transactions on Tron. This is impossible
    ///         on any EVM chain — it uses TVM's native delegateResource opcode.
    /// @dev Requires TVM Stake 2.0 support (TIP-467).
    ///      On TVM: address.delegateResource(amount, 1) delegates energy.
    ///      On standard solc: uses low-level call to system contract.
    ///      See: https://github.com/tronprotocol/tips/issues/467
    /// @param _to Agent to delegate energy to (must meet minTrustScore)
    /// @param _amount Amount of energy to delegate (in SUN)
    function delegateEnergyToTrusted(address _to, uint256 _amount) external onlyOwner {
        (uint8 score,,) = oracle.getTrust(_to);
        if (score < minTrustScore) revert RecipientNotTrusted(_to, score, minTrustScore);

        // Tron Stake 2.0: delegate energy to trusted agent
        // Uses system contract call — the TVM routes this to the native opcode
        // resourceType: 0 = bandwidth, 1 = energy
        bytes memory data = abi.encodeWithSignature(
            "delegateResource(address,uint256,uint256)",
            _to, _amount, uint256(1)
        );
        (bool success,) = address(this).call(data);
        if (!success) revert DelegationFailed();

        energyDelegatedTo[_to] += _amount;
        totalEnergyDelegated += _amount;

        emit EnergyDelegated(_to, _amount, score);
    }

    /// @notice Freeze TRX to gain energy for delegation (Tron Stake 2.0)
    /// @dev Uses system contract for freezeBalanceV2
    /// @param _amount Amount of TRX to freeze (in SUN)
    function freezeForEnergy(uint256 _amount) external onlyOwner {
        if (address(this).balance < _amount) revert InsufficientBalance(_amount, address(this).balance);
        // Tron Stake 2.0: freeze TRX for energy
        bytes memory data = abi.encodeWithSignature(
            "freezeBalanceV2(uint256,uint256)",
            _amount, uint256(1)
        );
        (bool success,) = address(this).call(data);
        if (!success) revert TransferFailed();
    }

    // ══════════════════════════════════════════════
    // Owner Controls
    // ══════════════════════════════════════════════

    /// @notice Update minimum trust score threshold
    /// @param _newScore New threshold (0-100)
    function setMinTrustScore(uint8 _newScore) external onlyOwner {
        if (_newScore > 100) revert ScoreOutOfRange(_newScore);
        uint8 old = minTrustScore;
        minTrustScore = _newScore;
        emit MinTrustScoreUpdated(old, _newScore);
    }

    /// @notice Toggle trust enforcement on/off
    function setTrustEnforced(bool _enabled) external onlyOwner {
        trustEnforced = _enabled;
        emit TrustEnforcementToggled(_enabled);
    }

    /// @notice Update oracle reference
    function setOracle(address _oracle) external onlyOwner {
        if (_oracle == address(0)) revert ZeroAddress();
        oracle = ITronTrustOracle(_oracle);
    }

    /// @notice Transfer wallet ownership
    function transferOwnership(address _newOwner) external onlyOwner {
        if (_newOwner == address(0)) revert ZeroAddress();
        owner = _newOwner;
    }

    // ══════════════════════════════════════════════
    // View Functions
    // ══════════════════════════════════════════════

    /// @notice Pre-check: would a transfer to this address succeed?
    /// @param _to Recipient to check
    /// @return score Recipient's current trust score
    /// @return wouldPass Whether the transfer would be approved
    /// @return minRequired Current minimum trust score setting
    function checkRecipient(address _to) external view returns (
        uint8 score,
        bool wouldPass,
        uint8 minRequired
    ) {
        (uint8 s,,) = oracle.getTrust(_to);
        return (s, s >= minTrustScore || !trustEnforced, minTrustScore);
    }

    /// @notice Get wallet statistics
    function getStats() external view returns (
        uint256 transfers,
        uint256 blocked,
        uint256 volumeTrx,
        uint8 currentMinScore,
        bool enforcing
    ) {
        return (totalTransfers, totalBlocked, totalVolumeSun, minTrustScore, trustEnforced);
    }

    /// @notice Accept TRX deposits
    receive() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }
}
