@echo off
rem Variante : sd-server seul avec son interface web integree (sans outil de dessin) sur http://127.0.0.1:1234/
cd /d "%~dp0sdcpp\vulkan"
sd-server.exe --diffusion-model "%~dp0models\diffusion_models\qwen-image-2.1-Q4_K_M.gguf" --vae "%~dp0models\vae\qwen_image_2.1_vae_bf16.safetensors" --llm "%~dp0models\text_encoders\qwen3vl_8b_int8_convrot_embfix.safetensors" --backend diffusion=vulkan0,vae=vulkan0,te=cpu --offload-to-cpu --listen-ip 127.0.0.1 --listen-port 1234 --cfg-scale 1.0 --sampling-method euler
