# DLCoalSim Web

Static Vue browser for DLCoalSim dataset metadata and sample previews.

```bash
npm install
python3 scripts/build_web_index.py \
  --dataset-dir /Users/larryivanhan/Desktop/DLCoalSim-10Mb-v1 \
  --out public/data \
  --hf-repo Larrivhan/DLCoalSim-10Mb-v1
npm run dev
```

The site reads small static JSON indexes. Raw shard data stays on Hugging Face.
