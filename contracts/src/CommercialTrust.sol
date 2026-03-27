// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CommercialTrust {
    // --- Roles ---
    address public owner;
    mapping(address => bool) public authorizedCallers; // PayClaw contract(s)

    // --- Structs ---
    struct CommercialRelationship {
        address partyA;
        address partyB;
        uint256 invoicesTotal;
        uint256 invoicesPaid;
        uint256 invoicesOverdue;
        uint256 avgPaymentDays;   // weighted average
        uint256 totalVolumeUsdt;  // 6-decimal USDT units
        uint8 relationshipScore;  // 0-100
        uint256 lastUpdated;
        bool exists;
    }

    // --- Storage ---
    mapping(bytes32 => CommercialRelationship) public relationships;
    mapping(address => uint8) public commercialScores; // aggregate per-wallet
    mapping(address => uint256) public walletInvoiceCount;
    mapping(address => uint256) public walletPaidCount;

    // --- Events ---
    event PaymentRecorded(
        address indexed payer,
        address indexed payee,
        uint256 amountUsdt,
        uint256 daysToPayment,
        bool wasOverdue
    );
    event RelationshipScoreUpdated(bytes32 indexed relationshipKey, uint8 score);
    event CommercialScoreUpdated(address indexed wallet, uint8 score);
    event CallerAuthorized(address indexed caller);
    event CallerRevoked(address indexed caller);

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "CommercialTrust: not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(authorizedCallers[msg.sender] || msg.sender == owner, "CommercialTrust: not authorized");
        _;
    }

    // --- Constructor ---
    constructor() {
        owner = msg.sender;
    }

    // --- Owner Functions ---
    function authorizeCaller(address _caller) external onlyOwner {
        authorizedCallers[_caller] = true;
        emit CallerAuthorized(_caller);
    }

    function revokeCaller(address _caller) external onlyOwner {
        authorizedCallers[_caller] = false;
        emit CallerRevoked(_caller);
    }

    // --- Core: Record Invoice Payment ---
    function recordInvoicePayment(
        address _payer,
        address _payee,
        uint256 _amountUsdt,
        uint256 _daysToPayment,
        bool _wasOverdue
    ) external onlyAuthorized {
        require(_payer != address(0) && _payee != address(0), "CommercialTrust: zero address");
        require(_payer != _payee, "CommercialTrust: self-payment");

        bytes32 key = _relationshipKey(_payer, _payee);
        CommercialRelationship storage rel = relationships[key];

        if (!rel.exists) {
            rel.partyA = _payer < _payee ? _payer : _payee;
            rel.partyB = _payer < _payee ? _payee : _payer;
            rel.exists = true;
        }

        rel.invoicesTotal++;
        rel.totalVolumeUsdt += _amountUsdt;

        if (_wasOverdue) {
            rel.invoicesOverdue++;
        } else {
            rel.invoicesPaid++;
        }

        // Weighted average payment days
        if (rel.invoicesTotal == 1) {
            rel.avgPaymentDays = _daysToPayment;
        } else {
            rel.avgPaymentDays = (rel.avgPaymentDays * (rel.invoicesTotal - 1) + _daysToPayment) / rel.invoicesTotal;
        }

        // Recalculate relationship score
        rel.relationshipScore = _calculateRelationshipScore(rel);
        rel.lastUpdated = block.timestamp;

        // Update per-wallet aggregates
        walletInvoiceCount[_payer]++;
        if (!_wasOverdue) walletPaidCount[_payer]++;

        commercialScores[_payer] = _calculateWalletScore(_payer);
        commercialScores[_payee] = _calculateWalletScore(_payee);

        emit PaymentRecorded(_payer, _payee, _amountUsdt, _daysToPayment, _wasOverdue);
        emit RelationshipScoreUpdated(key, rel.relationshipScore);
        emit CommercialScoreUpdated(_payer, commercialScores[_payer]);
    }

    // --- View Functions ---
    function getCommercialScore(address _a, address _b) external view returns (uint8) {
        bytes32 key = _relationshipKey(_a, _b);
        if (!relationships[key].exists) return 50; // neutral default
        return relationships[key].relationshipScore;
    }

    function getRecommendedTerms(address _buyer, address _merchant) external view returns (
        uint256 paymentWindowDays,
        bool requiresEscrow,
        uint256 creditLimitUsdt
    ) {
        uint8 buyerScore = commercialScores[_buyer];
        if (buyerScore == 0 && walletInvoiceCount[_buyer] == 0) buyerScore = 50;

        if (buyerScore >= 80) {
            return (30, false, 100000 * 1e6);       // net-30, no escrow, 100k USDT
        } else if (buyerScore >= 60) {
            return (14, false, 25000 * 1e6);         // net-14, no escrow, 25k USDT
        } else if (buyerScore >= 40) {
            return (7, true, 5000 * 1e6);            // net-7, escrow, 5k USDT
        } else {
            return (0, true, 1000 * 1e6);            // prepay, escrow, 1k USDT
        }
    }

    function getRelationship(address _a, address _b) external view returns (
        uint256 invoicesTotal,
        uint256 invoicesPaid,
        uint256 invoicesOverdue,
        uint256 avgPaymentDays,
        uint256 totalVolumeUsdt,
        uint8 relationshipScore
    ) {
        bytes32 key = _relationshipKey(_a, _b);
        CommercialRelationship memory rel = relationships[key];
        return (
            rel.invoicesTotal,
            rel.invoicesPaid,
            rel.invoicesOverdue,
            rel.avgPaymentDays,
            rel.totalVolumeUsdt,
            rel.relationshipScore
        );
    }

    // --- Internal ---
    function _relationshipKey(address _a, address _b) internal pure returns (bytes32) {
        (address low, address high) = _a < _b ? (_a, _b) : (_b, _a);
        return keccak256(abi.encodePacked(low, high));
    }

    function _calculateRelationshipScore(CommercialRelationship memory rel) internal pure returns (uint8) {
        if (rel.invoicesTotal == 0) return 50;

        // Payment rate: 60% weight
        uint256 paidRate = (rel.invoicesPaid * 100) / rel.invoicesTotal;
        uint256 paymentComponent = (paidRate * 60) / 100;

        // Speed: 25% weight (faster = better, capped at 30 days)
        uint256 speedScore;
        if (rel.avgPaymentDays <= 3) speedScore = 100;
        else if (rel.avgPaymentDays <= 7) speedScore = 85;
        else if (rel.avgPaymentDays <= 14) speedScore = 70;
        else if (rel.avgPaymentDays <= 30) speedScore = 50;
        else speedScore = 20;
        uint256 speedComponent = (speedScore * 25) / 100;

        // Volume: 15% weight (more volume = more trust, log scale approximation)
        uint256 volumeScore;
        uint256 vol = rel.totalVolumeUsdt / 1e6; // to whole USDT
        if (vol >= 100000) volumeScore = 100;
        else if (vol >= 10000) volumeScore = 80;
        else if (vol >= 1000) volumeScore = 60;
        else if (vol >= 100) volumeScore = 40;
        else volumeScore = 20;
        uint256 volumeComponent = (volumeScore * 15) / 100;

        uint256 total = paymentComponent + speedComponent + volumeComponent;
        if (total > 100) total = 100;
        return uint8(total);
    }

    function _calculateWalletScore(address _wallet) internal view returns (uint8) {
        if (walletInvoiceCount[_wallet] == 0) return 50;
        uint256 rate = (walletPaidCount[_wallet] * 100) / walletInvoiceCount[_wallet];
        if (rate > 100) rate = 100;
        return uint8(rate);
    }
}
