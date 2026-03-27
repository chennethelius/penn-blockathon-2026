const TronTrustOracle = artifacts.require("TronTrustOracle");
const TrustPassport = artifacts.require("TrustPassport");
const TrustGateContract = artifacts.require("TrustGateContract");
const CommercialTrust = artifacts.require("CommercialTrust");
const TrustEscrow = artifacts.require("TrustEscrow");

module.exports = async function (deployer, network, accounts) {
  const operatorAddress = accounts[0]; // deployer doubles as operator for testnet

  // 1. Deploy Oracle
  await deployer.deploy(TronTrustOracle, operatorAddress);
  const oracle = await TronTrustOracle.deployed();
  console.log("TronTrustOracle deployed at:", oracle.address);

  // 2. Deploy Passport
  await deployer.deploy(TrustPassport, operatorAddress);
  const passport = await TrustPassport.deployed();
  console.log("TrustPassport deployed at:", passport.address);

  // 3. Deploy TrustGate with oracle reference, default minScore=60
  await deployer.deploy(TrustGateContract, oracle.address, 60);
  const gate = await TrustGateContract.deployed();
  console.log("TrustGateContract deployed at:", gate.address);

  // 4. Deploy CommercialTrust
  await deployer.deploy(CommercialTrust);
  const commercial = await CommercialTrust.deployed();
  console.log("CommercialTrust deployed at:", commercial.address);

  // 5. Deploy TrustEscrow (oracle ref, arbiter = deployer, fee recipient = deployer)
  await deployer.deploy(TrustEscrow, oracle.address, operatorAddress, operatorAddress);
  const escrow = await TrustEscrow.deployed();
  console.log("TrustEscrow deployed at:", escrow.address);

  console.log("\n--- Deployment Summary ---");
  console.log("Oracle:     ", oracle.address);
  console.log("Passport:   ", passport.address);
  console.log("TrustGate:  ", gate.address);
  console.log("Commercial: ", commercial.address);
  console.log("Escrow:     ", escrow.address);
};
