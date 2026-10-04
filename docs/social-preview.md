# Social share preview

The homepage and research page share [social-preview-2026.png](../assets/social-preview-2026.png). Each page keeps its own title, description and canonical production URL in server-rendered Open Graph and large-image card metadata.

- Native generated image: **1730 × 909 PNG**, approximately **1.90:1**. Metadata records these actual dimensions; the requested size in the prompt was a composition target, not the returned raster size.
- Created on **2026-10-04** with the built-in image generation tool; copied without raster modification. No stock photograph, third-party logo or reference image was supplied.
- Navy, cyan and lime follow [the website tokens](../styles/tokens.css). Large Korean type keeps the title legible in small previews.
- The glowing map is a **stylized branding illustration**. Its relief and highlights are decorative, not measured terrain, regional counts, venue markers or source-backed geographic data. The interactive website retains its own [validated map](../data/national-map.v1.json).
- Text avoids changing case counts and claims of current operation. It says “전국 17개 시·도의 공개자료를 한눈에”.
- The build already publishes PNG assets from `assets/`; no new runtime dependency or build exception is needed.
- Metadata follows the [Open Graph protocol](https://ogp.me/) and uses `summary_large_image` for X-compatible cards. The image URL is absolute HTTPS and includes descriptive alternative text. Platform caches and crops are controlled by each platform; markup and public image availability are verified independently.
- Future visual replacements should use a new versioned asset URL, then update both pages and the true image dimensions.

## Final generation prompt

```text
Use case: ads-marketing.
Asset type: a finished premium Open Graph social share thumbnail for a Korean school esports map website, wide landscape composition with exact 1200 x 630 pixel output (1.905:1). Make ONE outstanding, publication-ready cover image.
Creative direction: contemporary professional esports broadcast identity meets beautifully restrained digital cartography. Confident editorial typography, sophisticated high contrast, precise fine details, not an amateur gaming poster.
Palette from the real site: almost black midnight navy #070b12 and #101a28, luminous cyan #42d9f3, sharply limited electric lime #d5ff45, clean near-white #f2f6fc.
Composition: strong asymmetrical wide layout. Left 58% holds very large, immaculate modern Korean sans-serif title with substantial breathing room and a bold lime 2026. Right 42% is a visually striking near-upright extruded glass/metal relief silhouette of SOUTH KOREA (Republic of Korea only, unmistakable correct outline, including small Jeju island southwest), luminous cyan edge lighting with a few lime glints. The map is an artistic brand illustration, not a data chart: no regional borders, no point markers, no counts, no geographic labels, no fictional statistics. Subtle laser-like diagonal light trails and restrained technical grid behind the map. Perspective should be only slightly tilted, silhouette remains recognizable. Refined dark atmosphere with crisp bright edges, cinematic 3D polish without haze washing out text.
Typography must look like beautiful Pretendard or a similarly premium neo-grotesque Korean sans serif, NOT rounded cartoon lettering, NOT pixel font, NOT faux futuristic angular Hangul. Main Korean title LARGE and readable at tiny social preview size. Absolutely exact Hangul spelling and Latin letter capitalization. Clean typesetting, not floating UI panels. Keep ALL type within a generous 60-pixel safe margin, nothing clipped. No borders.
Text verbatim, and only these strings:
Small top-left kicker: "SCHOLASTIC ESPORTS / KOREA"
Main title on two lines: "학교 e스포츠" then "지형도"
Large year below title: "2026"
Single secondary line below year: "전국 17개 시·도의 공개자료를 한눈에"
Use near-white for the main title, vivid lime for 2026, cool pale gray for the subtitle.
Avoid: people, controllers, headsets, trophies, sponsor or game logos, new invented logos, badges, buttons, flags, watermarks, pseudo-data widgets, clutter, illegible tiny type, generic stock art, excessive particles, excessive glow. The final result must feel like a designed prestige esports atlas cover.
```
