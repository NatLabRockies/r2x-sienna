import { defineConfig } from "astro/config";
import mermaid from "astro-mermaid";
import starlight from "@astrojs/starlight";
import { unified } from "@astrojs/markdown-remark";

export default defineConfig({
  site: "https://natlabrockies.github.io",
  base: "/r2x-sienna/",
  outDir: "./_build",
  markdown: { processor: unified() },
  redirects: {
  "/explanations/": "/r2x-sienna/explanation/",
  "/references/": "/r2x-sienna/reference/",
  "/how-tos/": "/r2x-sienna/how-to/python/"
},
  integrations: [
    mermaid({ enableLog: false, mermaidConfig: { theme: "base", fontFamily: "system-ui, sans-serif", flowchart: { curve: "basis", nodeSpacing: 35, rankSpacing: 45, padding: 16 } } }),
    starlight({
    title: "r2x-sienna",
    logo: {
      light: "./src/assets/r2x-logo-full-color.svg",
      dark: "./src/assets/r2x-logo-white.svg",
      alt: "R2X",
      replacesTitle: false,
    },
    social: [{ icon: "github", label: "GitHub", href: "https://github.com/NatLabRockies/r2x-sienna" }],
    editLink: { baseUrl: "https://github.com/NatLabRockies/r2x-sienna/edit/main/docs/src/content/docs/" },
    customCss: ["./src/styles/brand.css"],
    sidebar: [
  {
    "label": "Getting started",
    "items": [
      {
        "label": "Installation",
        "link": "/getting-started/installation/"
      },
      {
        "label": "Environment and prerequisites",
        "link": "/getting-started/environment/"
      },
      {
        "label": "Verify installation and first use",
        "link": "/getting-started/verify/"
      }
    ]
  },
  {
    "label": "Tutorials",
    "items": [
      {
        "label": "Introduction",
        "link": "/"
      },
      {
        "label": "Parse and export",
        "link": "/tutorials/round-trip/"
      }
    ]
  },
  {
    "label": "How-to guides",
    "items": [
      {
        "label": "Python workflow",
        "link": "/how-to/python/"
      },
      {
        "label": "Inspect an archive",
        "link": "/how-to/inspect-system/"
      },
      {
        "label": "CLI pipeline",
        "link": "/how-to/pipeline/"
      }
    ]
  },
  {
    "label": "Reference / API",
    "items": [
      {
        "label": "Public API and configuration",
        "link": "/reference/"
      },
      {
        "label": "Model catalog",
        "link": "/reference/models/"
      },
      {
        "label": "Units",
        "link": "/reference/units/"
      },
      {
        "label": "Functions and curves",
        "link": "/reference/functions/"
      }
    ]
  },
  {
    "label": "Explanation",
    "items": [
      {
        "label": "Sienna upgrades and storage",
        "link": "/explanation/"
      },
      {
        "label": "Upgrader design",
        "link": "/explanation/upgrader/"
      },
      {
        "label": "Models and units",
        "link": "/explanation/models-and-units/"
      }
    ]
  },
  {
    "label": "Troubleshooting",
    "items": [
      {
        "label": "Common problems",
        "link": "/troubleshooting/"
      }
    ]
  },
  {
    "label": "Changelog",
    "link": "/changelog/"
  },
  {
    "label": "Contributors",
    "items": [
      {
        "label": "Development",
        "link": "/contributors/"
      }
    ]
  }
]
  })],
});
