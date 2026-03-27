// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract TrustPassport {
    // --- Roles ---
    address public owner;
    address public operator;

    // --- Passport Data ---
    struct Passport {
        uint256 tokenId;
        uint8 trustScore;
        uint8 commercialScore;
        string agentType;
        uint256 registeredAt;
        uint32 sunPoints;
        bool exists;
    }

    // --- Storage ---
    mapping(address => Passport) public passports;
    mapping(uint256 => address) public tokenOwners;
    mapping(address => uint256) public addressToTokenId;

    uint256 public totalSupply;
    string public name = "TronTrust Passport";
    string public symbol = "TTPAS";

    // --- Events ---
    event PassportMinted(address indexed to, uint256 tokenId, string agentType);
    event ScoreUpdated(address indexed agent, uint8 trustScore, uint8 commercialScore);
    event SunPointsAdded(address indexed agent, uint32 points, uint32 newTotal);
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "TrustPassport: not owner");
        _;
    }

    modifier onlyOperator() {
        require(msg.sender == operator, "TrustPassport: not operator");
        _;
    }

    // --- Constructor ---
    constructor(address _operator) {
        owner = msg.sender;
        operator = _operator;
    }

    // --- Owner ---
    function setOperator(address _operator) external onlyOwner {
        operator = _operator;
    }

    // --- Operator Functions ---
    function mint(address _to, string calldata _agentType) external onlyOperator returns (uint256) {
        require(!passports[_to].exists, "TrustPassport: already has passport");

        totalSupply++;
        uint256 tokenId = totalSupply;

        passports[_to] = Passport({
            tokenId: tokenId,
            trustScore: 50,
            commercialScore: 50,
            agentType: _agentType,
            registeredAt: block.timestamp,
            sunPoints: 0,
            exists: true
        });

        tokenOwners[tokenId] = _to;
        addressToTokenId[_to] = tokenId;

        emit PassportMinted(_to, tokenId, _agentType);
        emit Transfer(address(0), _to, tokenId);
        return tokenId;
    }

    function updateScore(address _agent, uint8 _trustScore, uint8 _commercialScore) external onlyOperator {
        require(passports[_agent].exists, "TrustPassport: no passport");
        require(_trustScore <= 100 && _commercialScore <= 100, "TrustPassport: score out of range");

        passports[_agent].trustScore = _trustScore;
        passports[_agent].commercialScore = _commercialScore;

        emit ScoreUpdated(_agent, _trustScore, _commercialScore);
    }

    function addSunPoints(address _agent, uint32 _points) external onlyOperator {
        require(passports[_agent].exists, "TrustPassport: no passport");

        passports[_agent].sunPoints += _points;
        emit SunPointsAdded(_agent, _points, passports[_agent].sunPoints);
    }

    // --- Soul-bound: block all transfers ---
    function transferFrom(address, address, uint256) external pure {
        revert("TrustPassport: soul-bound, non-transferable");
    }

    function safeTransferFrom(address, address, uint256) external pure {
        revert("TrustPassport: soul-bound, non-transferable");
    }

    function approve(address, uint256) external pure {
        revert("TrustPassport: soul-bound, non-transferable");
    }

    // --- View Functions ---
    function getPassport(address _agent) external view returns (
        uint256 tokenId,
        uint8 trustScore,
        uint8 commercialScore,
        string memory agentType,
        uint256 registeredAt,
        uint32 sunPoints
    ) {
        require(passports[_agent].exists, "TrustPassport: no passport");
        Passport memory p = passports[_agent];
        return (p.tokenId, p.trustScore, p.commercialScore, p.agentType, p.registeredAt, p.sunPoints);
    }

    function ownerOf(uint256 _tokenId) external view returns (address) {
        address o = tokenOwners[_tokenId];
        require(o != address(0), "TrustPassport: nonexistent token");
        return o;
    }

    function balanceOf(address _owner) external view returns (uint256) {
        return passports[_owner].exists ? 1 : 0;
    }

    // --- On-chain SVG tokenURI ---
    function tokenURI(uint256 _tokenId) external view returns (string memory) {
        address agent = tokenOwners[_tokenId];
        require(agent != address(0), "TrustPassport: nonexistent token");

        Passport memory p = passports[agent];
        string memory verdictColor = _getVerdictColor(p.trustScore);

        return string(abi.encodePacked(
            "data:image/svg+xml;utf8,",
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="250" style="background:#0a0a0a;border-radius:16px">',
            '<text x="200" y="40" text-anchor="middle" fill="#fff" font-size="18" font-family="monospace">TronTrust Passport</text>',
            '<circle cx="200" cy="120" r="50" fill="', verdictColor, '"/>',
            '<text x="200" y="130" text-anchor="middle" fill="#fff" font-size="32" font-family="monospace">', _uint8ToString(p.trustScore), '</text>',
            '<text x="200" y="190" text-anchor="middle" fill="#888" font-size="12" font-family="monospace">', p.agentType, '</text>',
            '<text x="60" y="230" fill="#666" font-size="11" font-family="monospace">Commercial: ', _uint8ToString(p.commercialScore), '</text>',
            '<text x="260" y="230" fill="#666" font-size="11" font-family="monospace">Sun: ', _uint32ToString(p.sunPoints), '</text>',
            '</svg>'
        ));
    }

    // --- Internal Helpers ---
    function _getVerdictColor(uint8 score) internal pure returns (string memory) {
        if (score >= 80) return "#22c55e";       // green - trusted
        if (score >= 60) return "#3b82f6";       // blue - proceed
        if (score >= 40) return "#f59e0b";       // amber - caution
        return "#ef4444";                         // red - avoid
    }

    function _uint8ToString(uint8 value) internal pure returns (string memory) {
        if (value == 0) return "0";
        uint8 temp = value;
        uint8 digits;
        while (temp != 0) { digits++; temp /= 10; }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits--;
            buffer[digits] = bytes1(uint8(48 + value % 10));
            value /= 10;
        }
        return string(buffer);
    }

    function _uint32ToString(uint32 value) internal pure returns (string memory) {
        if (value == 0) return "0";
        uint32 temp = value;
        uint8 digits;
        while (temp != 0) { digits++; temp /= 10; }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits--;
            buffer[digits] = bytes1(uint8(48 + value % 10));
            value /= 10;
        }
        return string(buffer);
    }
}
