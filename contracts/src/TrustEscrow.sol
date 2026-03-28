// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

/**
 * @title TrustEscrow
 * @notice Trust-gated escrow for AI agent commerce on Tron.
 *
 * Escrow release conditions depend on the buyer's trust score:
 *   - Score >= 80: instant release (no escrow hold)
 *   - Score >= 60: 24h hold, then auto-release
 *   - Score >= 40: requires seller confirmation OR 7-day timeout
 *   - Score < 40:  requires seller confirmation AND arbiter approval
 *
 * Supports TRX and TRC-20 (USDT) deposits.
 */

interface ITronTrustOracle {
    function getTrust(address _agent) external view returns (uint8 score, uint8 verdict, bool isTrusted);
}

interface ITRC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract TrustEscrow {
    // --- Enums ---
    enum EscrowStatus { Active, Released, Refunded, Disputed }
    enum ReleaseType { Instant, TimeLocked, SellerConfirm, ArbiterRequired }

    // --- Structs ---
    struct Escrow {
        address buyer;
        address seller;
        uint256 amount;
        address token;           // address(0) = TRX, else TRC-20 contract
        uint8 buyerTrustScore;
        ReleaseType releaseType;
        EscrowStatus status;
        uint256 createdAt;
        uint256 releaseAfter;    // timestamp when auto-release is allowed
        bool sellerConfirmed;
        bool arbiterApproved;
    }

    // --- State ---
    ITronTrustOracle public oracle;
    address public arbiter;
    address public owner;

    uint256 public escrowCount;
    mapping(uint256 => Escrow) public escrows;

    // Fee: 0.5% to protocol
    uint256 public constant FEE_BPS = 50; // 0.5%
    address public feeRecipient;
    uint256 public totalFeesCollected;

    // --- Events ---
    event EscrowCreated(uint256 indexed escrowId, address indexed buyer, address indexed seller, uint256 amount, address token, ReleaseType releaseType);
    event EscrowReleased(uint256 indexed escrowId, address indexed seller, uint256 amount, uint256 fee);
    event EscrowRefunded(uint256 indexed escrowId, address indexed buyer, uint256 amount);
    event SellerConfirmed(uint256 indexed escrowId);
    event ArbiterApproved(uint256 indexed escrowId);
    event Disputed(uint256 indexed escrowId, address indexed disputor);

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "TrustEscrow: not owner");
        _;
    }

    modifier onlyArbiter() {
        require(msg.sender == arbiter, "TrustEscrow: not arbiter");
        _;
    }

    // --- Constructor ---
    constructor(address _oracle, address _arbiter, address _feeRecipient) {
        oracle = ITronTrustOracle(_oracle);
        arbiter = _arbiter;
        feeRecipient = _feeRecipient;
        owner = msg.sender;
    }

    // --- Create Escrow (TRX) ---
    function createEscrowTRX(address _seller) external payable returns (uint256) {
        require(msg.value > 0, "TrustEscrow: zero amount");
        return _createEscrow(msg.sender, _seller, msg.value, address(0));
    }

    // --- Create Escrow (TRC-20) ---
    function createEscrowTRC20(address _seller, address _token, uint256 _amount) external returns (uint256) {
        require(_amount > 0, "TrustEscrow: zero amount");
        require(ITRC20(_token).transferFrom(msg.sender, address(this), _amount), "TrustEscrow: transfer failed");
        return _createEscrow(msg.sender, _seller, _amount, _token);
    }

    // --- Release ---
    function release(uint256 _escrowId) external {
        Escrow storage e = escrows[_escrowId];
        require(e.status == EscrowStatus.Active, "TrustEscrow: not active");

        if (e.releaseType == ReleaseType.Instant) {
            // Buyer trust >= 80: anyone can release immediately
        } else if (e.releaseType == ReleaseType.TimeLocked) {
            // Buyer trust >= 60: auto-release after time lock
            require(block.timestamp >= e.releaseAfter, "TrustEscrow: time lock active");
        } else if (e.releaseType == ReleaseType.SellerConfirm) {
            // Buyer trust >= 40: seller must confirm OR timeout (7 days)
            require(
                e.sellerConfirmed || block.timestamp >= e.releaseAfter,
                "TrustEscrow: awaiting seller confirmation"
            );
        } else {
            // Buyer trust < 40: seller confirm AND arbiter approval
            require(e.sellerConfirmed && e.arbiterApproved, "TrustEscrow: awaiting arbiter");
        }

        _doRelease(_escrowId);
    }

    // --- Seller confirms delivery ---
    function confirmDelivery(uint256 _escrowId) external {
        Escrow storage e = escrows[_escrowId];
        require(msg.sender == e.seller, "TrustEscrow: not seller");
        require(e.status == EscrowStatus.Active, "TrustEscrow: not active");
        e.sellerConfirmed = true;
        emit SellerConfirmed(_escrowId);

        // Auto-release if conditions met
        if (e.releaseType == ReleaseType.SellerConfirm) {
            _doRelease(_escrowId);
        } else if (e.releaseType == ReleaseType.ArbiterRequired && e.arbiterApproved) {
            _doRelease(_escrowId);
        }
    }

    // --- Arbiter approves ---
    function arbiterApprove(uint256 _escrowId) external onlyArbiter {
        Escrow storage e = escrows[_escrowId];
        require(e.status == EscrowStatus.Active, "TrustEscrow: not active");
        e.arbiterApproved = true;
        emit ArbiterApproved(_escrowId);

        if (e.sellerConfirmed) {
            _doRelease(_escrowId);
        }
    }

    // --- Refund (buyer can refund if seller hasn't confirmed within timeout) ---
    function refund(uint256 _escrowId) external {
        Escrow storage e = escrows[_escrowId];
        require(e.status == EscrowStatus.Active, "TrustEscrow: not active");
        require(msg.sender == e.buyer || msg.sender == arbiter, "TrustEscrow: not authorized");
        require(!e.sellerConfirmed, "TrustEscrow: seller already confirmed");
        require(block.timestamp >= e.releaseAfter, "TrustEscrow: too early for refund");

        e.status = EscrowStatus.Refunded;
        _transferOut(e.token, e.buyer, e.amount);
        emit EscrowRefunded(_escrowId, e.buyer, e.amount);
    }

    // --- Dispute ---
    function dispute(uint256 _escrowId) external {
        Escrow storage e = escrows[_escrowId];
        require(e.status == EscrowStatus.Active, "TrustEscrow: not active");
        require(msg.sender == e.buyer || msg.sender == e.seller, "TrustEscrow: not party");
        e.status = EscrowStatus.Disputed;
        emit Disputed(_escrowId, msg.sender);
    }

    // --- View ---
    function getEscrow(uint256 _escrowId) external view returns (
        address buyer, address seller, uint256 amount, address token,
        uint8 buyerTrustScore, ReleaseType releaseType, EscrowStatus status,
        uint256 createdAt, uint256 releaseAfter, bool sellerConfirmed, bool arbiterApproved
    ) {
        Escrow memory e = escrows[_escrowId];
        return (e.buyer, e.seller, e.amount, e.token, e.buyerTrustScore,
                e.releaseType, e.status, e.createdAt, e.releaseAfter,
                e.sellerConfirmed, e.arbiterApproved);
    }

    // --- Admin ---
    function setArbiter(address _arbiter) external onlyOwner {
        arbiter = _arbiter;
    }

    function setOracle(address _oracle) external onlyOwner {
        oracle = ITronTrustOracle(_oracle);
    }

    // --- Internal ---
    function _createEscrow(address _buyer, address _seller, uint256 _amount, address _token) internal returns (uint256) {
        require(_buyer != _seller, "TrustEscrow: self-escrow");

        (uint8 score,,) = oracle.getTrust(_buyer);
        ReleaseType rt;
        uint256 releaseAfter;

        if (score >= 80) {
            rt = ReleaseType.Instant;
            releaseAfter = block.timestamp; // immediate
        } else if (score >= 60) {
            rt = ReleaseType.TimeLocked;
            releaseAfter = block.timestamp + 1 days;
        } else if (score >= 40) {
            rt = ReleaseType.SellerConfirm;
            releaseAfter = block.timestamp + 7 days;
        } else {
            rt = ReleaseType.ArbiterRequired;
            releaseAfter = block.timestamp + 14 days;
        }

        escrowCount++;
        escrows[escrowCount] = Escrow({
            buyer: _buyer,
            seller: _seller,
            amount: _amount,
            token: _token,
            buyerTrustScore: score,
            releaseType: rt,
            status: EscrowStatus.Active,
            createdAt: block.timestamp,
            releaseAfter: releaseAfter,
            sellerConfirmed: false,
            arbiterApproved: false
        });

        emit EscrowCreated(escrowCount, _buyer, _seller, _amount, _token, rt);
        return escrowCount;
    }

    function _doRelease(uint256 _escrowId) internal {
        Escrow storage e = escrows[_escrowId];
        e.status = EscrowStatus.Released;

        uint256 fee = (e.amount * FEE_BPS) / 10000;
        uint256 payout = e.amount - fee;

        _transferOut(e.token, e.seller, payout);
        if (fee > 0) {
            _transferOut(e.token, feeRecipient, fee);
            totalFeesCollected += fee;
        }

        emit EscrowReleased(_escrowId, e.seller, payout, fee);
    }

    function _transferOut(address _token, address _to, uint256 _amount) internal {
        if (_token == address(0)) {
            (bool ok,) = payable(_to).call{value: _amount}("");
            require(ok, "TrustEscrow: TRX transfer failed");
        } else {
            require(ITRC20(_token).transfer(_to, _amount), "TrustEscrow: TRC20 transfer failed");
        }
    }

    // Accept TRX
    receive() external payable {}
}
