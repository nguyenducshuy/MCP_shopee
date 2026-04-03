const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, LevelFormat } = require("docx");

const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
const cm = { top: 60, bottom: 60, left: 100, right: 100 };

function hCell(text, w) {
  return new TableCell({ borders, width: { size: w, type: WidthType.DXA },
    shading: { fill: "2E75B6", type: ShadingType.CLEAR }, margins: cm,
    children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, color: "FFFFFF", font: "Arial", size: 20 })] })] });
}

function c(text, w, opts = {}) {
  return new TableCell({ borders, width: { size: w, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined, margins: cm,
    children: [new Paragraph({ alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text, font: "Arial", size: 20, bold: opts.bold || false, color: opts.color || "000000" })] })] });
}

function sc(text, w) {
  return c(text === "OK" ? "\u2714 OK" : text, w, { bold: true, color: text === "OK" ? "27AE60" : "E74C3C", center: true });
}

const features = [
  ["1","Xem khung gi\u1EDD kh\u1EA3 d\u1EE5ng","L\u1EA5y danh s\u00E1ch slot gi\u1EDD Flash Sale c\u00F3 th\u1EC3 \u0111\u0103ng k\u00FD","OK"],
  ["2","T\u1EA1o phi\u00EAn Flash Sale","T\u1EA1o phi\u00EAn m\u1EDBi theo khung gi\u1EDD \u0111\u00E3 ch\u1ECDn","OK"],
  ["3","Xem chi ti\u1EBFt phi\u00EAn","Xem tr\u1EA1ng th\u00E1i, th\u1EDDi gian, s\u1ED1 SP c\u1EE7a 1 phi\u00EAn","OK"],
  ["4","Xem danh s\u00E1ch phi\u00EAn","L\u1ECDc theo upcoming / ongoing / expired","OK"],
  ["5","B\u1EADt/t\u1EAFt phi\u00EAn","B\u1EADt ho\u1EB7c t\u1EAFt to\u00E0n b\u1ED9 phi\u00EAn Flash Sale","OK"],
  ["6","X\u00F3a phi\u00EAn","X\u00F3a phi\u00EAn ch\u01B0a di\u1EC5n ra (upcoming)","OK"],
  ["7","Th\u00EAm s\u1EA3n ph\u1EA9m","\u0110\u01B0a SP v\u00E0o phi\u00EAn, h\u1ED7 tr\u1EE3 SP c\u00F3/kh\u00F4ng bi\u1EBFn th\u1EC3","OK"],
  ["8","Xem SP trong phi\u00EAn","Xem danh s\u00E1ch SP, gi\u00E1 KM, t\u1ED3n kho, tr\u1EA1ng th\u00E1i","OK"],
  ["9","C\u1EADp nh\u1EADt SP","S\u1EEDa gi\u00E1, t\u1ED3n kho, b\u1EADt/t\u1EAFt t\u1EEBng SP trong phi\u00EAn","OK"],
  ["10","X\u00F3a SP kh\u1ECFi phi\u00EAn","Lo\u1EA1i b\u1ECF SP kh\u00F4ng c\u1EA7n thi\u1EBFt","OK"],
  ["11","Ki\u1EC3m tra \u0111i\u1EC1u ki\u1EC7n SP","Xem ti\u00EAu ch\u00ED SP c\u1EA7n \u0111\u1EA1t \u0111\u1EC3 tham gia FS","OK"],
  ["12","T\u1EA1o FS h\u00E0ng lo\u1EA1t","T\u1EA1o Flash Sale nhi\u1EC1u shop c\u00F9ng l\u00FAc (batch)","OK"],
];

const fRows = [
  new TableRow({ children: [hCell("STT",600), hCell("Ch\u1EE9c n\u0103ng",2400), hCell("M\u00F4 t\u1EA3",4760), hCell("Tr\u1EA1ng th\u00E1i",1600)] }),
  ...features.map((f,i) => new TableRow({ children: [
    c(f[0],600,{center:true,fill:i%2===0?"F2F7FB":undefined}),
    c(f[1],2400,{bold:true,fill:i%2===0?"F2F7FB":undefined}),
    c(f[2],4760,{fill:i%2===0?"F2F7FB":undefined}),
    sc(f[3],1600)] }))
];

const tRows = [
  new TableRow({ children: [hCell("H\u1EA1ng m\u1EE5c",3500), hCell("K\u1EBFt qu\u1EA3",5860)] }),
  new TableRow({ children: [c("Shop test",3500,{bold:true}), c("Kid Center (production)",5860)] }),
  new TableRow({ children: [c("Ng\u00E0y test",3500,{bold:true,fill:"F2F7FB"}), c("30/03/2026",5860,{fill:"F2F7FB"})] }),
  new TableRow({ children: [c("K\u1EBFt qu\u1EA3",3500,{bold:true}), c("10/11 ch\u1EE9c n\u0103ng ch\u1EA1y th\u00E0nh c\u00F4ng",5860)] }),
  new TableRow({ children: [c("B\u1ECF qua",3500,{bold:true,fill:"F2F7FB"}), c("C\u1EADp nh\u1EADt SP (phi\u00EAn test kh\u00F4ng c\u00F3 SP b\u00EAn trong)",5860,{fill:"F2F7FB"})] }),
  new TableRow({ children: [c("L\u1ED7i g\u1EB7p",3500,{bold:true}), c("\"insufficient stock\" khi th\u00EAm SP \u2014 do SP h\u1EBFt t\u1ED3n kho, KH\u00D4NG ph\u1EA3i l\u1ED7i h\u1EC7 th\u1ED1ng",5860)] }),
  new TableRow({ children: [c("D\u1ECDn d\u1EB9p",3500,{bold:true,fill:"F2F7FB"}), c("Phi\u00EAn test \u0111\u00E3 \u0111\u01B0\u1EE3c x\u00F3a s\u1EA1ch sau khi test xong",5860,{fill:"F2F7FB"})] }),
];

const wf = [
  ["1","Ki\u1EC3m tra \u0111i\u1EC1u ki\u1EC7n SP","Xem ti\u00EAu ch\u00ED SP c\u1EA7n \u0111\u1EA1t tr\u01B0\u1EDBc khi ch\u1ECDn SP"],
  ["2","Xem khung gi\u1EDD tr\u1ED1ng","Ch\u1ECDn khung gi\u1EDD Flash Sale ph\u00F9 h\u1EE3p"],
  ["3","T\u1EA1o phi\u00EAn Flash Sale","T\u1EA1o phi\u00EAn m\u1EDBi v\u1EDBi khung gi\u1EDD \u0111\u00E3 ch\u1ECDn (phi\u00EAn r\u1ED7ng)"],
  ["4","Th\u00EAm SP v\u00E0o phi\u00EAn","\u0110\u01B0a s\u1EA3n ph\u1EA9m v\u00E0o, set gi\u00E1 khuy\u1EBFn m\u00E3i v\u00E0 t\u1ED3n kho"],
  ["5","B\u1EADt phi\u00EAn","K\u00EDch ho\u1EA1t phi\u00EAn Flash Sale"],
  ["6","Theo d\u00F5i","Ki\u1EC3m tra tr\u1EA1ng th\u00E1i SP, xem reject reason n\u1EBFu c\u00F3"],
];
const wfRows = [
  new TableRow({ children: [hCell("B\u01B0\u1EDBc",600), hCell("H\u00E0nh \u0111\u1ED9ng",3200), hCell("M\u00F4 t\u1EA3",5560)] }),
  ...wf.map((w,i) => new TableRow({ children: [
    c(w[0],600,{center:true,bold:true,fill:i%2===0?"F2F7FB":undefined}),
    c(w[1],3200,{bold:true,fill:i%2===0?"F2F7FB":undefined}),
    c(w[2],5560,{fill:i%2===0?"F2F7FB":undefined})] }))
];

function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })] });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
    ]
  },
  numbering: { config: [{ reference: "bullets",
    levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Shopee MCP Server \u2014 Flash Sale Module", font: "Arial", size: 16, color: "999999", italics: true })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Trang ", font: "Arial", size: 16, color: "999999" }),
        new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "999999" })] })] }) },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "B\u00C1O C\u00C1O", font: "Arial", size: 40, bold: true, color: "2E75B6" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 },
        children: [new TextRun({ text: "H\u1EC7 th\u1ED1ng Flash Sale t\u1EF1 \u0111\u1ED9ng \u2014 MCP Server", font: "Arial", size: 28, color: "444444" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "Ng\u00E0y: 30/03/2026", font: "Arial", size: 22, color: "666666" })] }),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("1. T\u1ED5ng quan")] }),
      new Paragraph({ spacing: { after: 200 }, children: [
        new TextRun({ text: "\u0110\u00E3 t\u00EDch h\u1EE3p \u0111\u1EA7y \u0111\u1EE7 ", font: "Arial", size: 22 }),
        new TextRun({ text: "11 ch\u1EE9c n\u0103ng Flash Sale", font: "Arial", size: 22, bold: true }),
        new TextRun({ text: " t\u1EEB Shopee Open Platform v\u00E0o h\u1EC7 th\u1ED1ng MCP Server. N\u00E2ng c\u1EA5p t\u1EEB 2 ch\u1EE9c n\u0103ng c\u0169 l\u00EAn 12 ch\u1EE9c n\u0103ng (11 API + 1 batch). \u0110\u00E3 test th\u00E0nh c\u00F4ng tr\u00EAn shop Kid Center (production).", font: "Arial", size: 22 }),
      ] }),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("2. Danh s\u00E1ch ch\u1EE9c n\u0103ng")] }),
      new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [600,2400,4760,1600], rows: fRows }),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("3. K\u1EBFt qu\u1EA3 test th\u1EF1c t\u1EBF")] }),
      new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [3500,5860], rows: tRows }),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("4. Lu\u1ED3ng v\u1EADn h\u00E0nh chu\u1EA9n")] }),
      new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [600,3200,5560], rows: wfRows }),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("5. L\u01B0u \u00FD quan tr\u1ECDng")] }),
      bullet("T\u1ED1i \u0111a 50 s\u1EA3n ph\u1EA9m \u0111\u01B0\u1EE3c b\u1EADt trong 1 phi\u00EAn Flash Sale."),
      bullet("Mu\u1ED1n s\u1EEDa gi\u00E1/t\u1ED3n kho SP \u0111ang b\u1EADt: ph\u1EA3i t\u1EAFt SP tr\u01B0\u1EDBc \u2192 s\u1EEDa \u2192 b\u1EADt l\u1EA1i."),
      bullet("Ch\u1EC9 x\u00F3a \u0111\u01B0\u1EE3c phi\u00EAn ch\u01B0a di\u1EC5n ra (upcoming)."),
      bullet("Shop ph\u1EA3i active v\u00E0 kh\u00F4ng \u1EDF ch\u1EBF \u0111\u1ED9 ngh\u1EC9 l\u1EC5 (holiday mode)."),
      bullet("SP ph\u1EA3i \u0111\u1EA1t ti\u00EAu ch\u00ED: rating, t\u1ED3n kho, % gi\u1EA3m gi\u00E1, ..."),

      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("6. B\u01B0\u1EDBc ti\u1EBFp theo")] }),
      bullet("Ph\u00F2ng kinh doanh cung c\u1EA5p danh s\u00E1ch SP c\u1EA7n set Flash Sale h\u00E0ng ng\u00E0y (Google Sheet)."),
      bullet("Team k\u1EF9 thu\u1EADt t\u00EDch h\u1EE3p v\u1EDBi Google Apps Script \u0111\u1EC3 t\u1EF1 \u0111\u1ED9ng h\u00F3a."),
      bullet("M\u1EDF r\u1ED9ng cho c\u00E1c shop kh\u00E1c ngo\u00E0i Kid Center."),
      bullet("X\u00E2y d\u1EF1ng dashboard theo d\u00F5i tr\u1EA1ng th\u00E1i Flash Sale to\u00E0n b\u1ED9 shop."),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("docs/BAO_CAO_FLASH_SALE_MCP.docx", buffer);
  console.log("OK: docs/BAO_CAO_FLASH_SALE_MCP.docx");
});
