const TrustWallet = artifacts.require("TrustWallet");

module.exports = async function (deployer) {
  const oracleAddress = "TJtw1YMJiWujvGns3gFKaQmgEbp36rmnqK";
  await deployer.deploy(TrustWallet, oracleAddress, 60);
  const wallet = await TrustWallet.deployed();
  console.log("TrustWallet deployed at:", wallet.address);
};
