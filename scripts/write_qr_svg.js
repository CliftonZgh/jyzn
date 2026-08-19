const QRCode = require("qrcode");

const [url, output] = process.argv.slice(2);

if (!url || !output) {
  throw new Error("usage: write_qr_svg.js <url> <output>");
}

QRCode.toFile(output, url, {
  type: "svg",
  errorCorrectionLevel: "M",
  margin: 4,
  color: {
    dark: "#000000",
    light: "#ffffff",
  },
});
