# 🎮 VoxelCraft

**VoxelCraft** is a Python-based Minecraft-style voxel sandbox game built using Pygame, NumPy, and ModernGL.

Explore procedurally generated terrain, break and place blocks, build structures, and save your own worlds!

## ✨ Features

- **First-Person Controls** – Mouse-based camera movement.
- **Procedural Terrain** – Automatically generated landscapes.
- **Chunk Generation** – Chunk-based world system.
- **Trees** – Procedurally generated trees.
- **Block Breaking & Placing** – Interact with the world.
- **Hotbar** – Select between 8 different block types.
- **Inventory** – Simple inventory interface.
- **Water** – Generated water at low terrain elevations.
- **Lighting & Shading** – Basic directional block shading.
- **Flight Mode** – Freely explore the world.
- **World Saving & Loading** – Save and load your progress.
- **Debug Overlay** – View FPS, coordinates, and chunk information.

## 🧱 Available Blocks

1. Grass
2. Dirt
3. Stone
4. Wood
5. Leaves
6. Sand
7. Water
8. Planks

## 💻 Requirements

- Python 3.13 recommended
- Pygame
- NumPy
- ModernGL
- OpenGL 3.3-compatible graphics driver

## 📦 Installation

Install the required Python libraries:

```bash
py -3.13 -m pip install pygame numpy moderngl
```

## ▶️ Running the Game

Navigate to the project directory and run:

```bash
py -3.13 main.py
```

## 🎮 Controls

| Key | Action |
|---|---|
| W A S D | Move |
| Mouse | Look around |
| Space | Jump / Fly upward |
| Shift | Fly downward |
| F | Toggle flight |
| Left Click | Break blocks |
| Right Click | Place blocks |
| 1–8 | Select hotbar slot |
| Mouse Wheel | Change selected block |
| E | Open / Close inventory |
| F3 | Toggle debug information |
| Esc | Release mouse |
| Enter | Capture mouse |
| F5 | Save world |
| F9 | Load world |
| Ctrl + S | Save world |
| Ctrl + L | Load world |

## 💾 World Saves

VoxelCraft automatically creates a `saves` folder when the world is saved.

World data is stored in:

```text
VoxelCraft/
├── main.py
├── README.md
└── saves/
    └── world.json
```

The save file stores the world seed and player-made block edits.

## ⚙️ Configuration

You can customize settings directly in `main.py`, including:

- Screen resolution
- Chunk size
- World height
- View distance
- Render distance
- Mouse sensitivity
- Walking speed
- Flying speed
- Gravity

## 🚧 Project Status

VoxelCraft is an actively developing sandbox prototype.

Some features that could be added in future updates:

- Multiplayer support
- More block types
- Crafting system
- Mobs and animals
- Sound effects
- Day and night cycle
- Improved lighting
- Texture support
- More advanced water rendering

## 🛠️ Built With

- [Python](https://www.python.org/)
- [Pygame](https://www.pygame.org/)
- [NumPy](https://numpy.org/)
- [ModernGL](https://moderngl.readthedocs.io/)

## 📜 License

No license has been selected yet.

Add a `LICENSE` file to the repository when you decide how others may use, modify, and distribute this project.

---

**Thanks for checking out VoxelCraft!** 🌍

Have fun exploring, building, and experimenting!
