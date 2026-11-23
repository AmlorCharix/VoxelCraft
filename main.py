
    
  
            elif event.type == pygame.MOUSEWHEEL:
                selected = (selected - event.y) % len(HOTBAR)
            elif event.type == pygame.MOUSEBUTTONDOWN and pygame.event.get_grab() and not inventory_open:
                if event.button in (1, 3):
                    hit, place = raycast(world, player.pos + np.array([0, -0.15, 0]), player.direction())
                    if hit:
                        if event.button == 1:
                            world.set(*hit, AIR)
                        elif place and world.get(*place) == AIR:
                            # Avoid placing a block inside the player's body.
                            px, py, pz = player.pos
                            if not (place[0] <= px + .3 and place[0] + 1 >= px - .3 and
                                    place[1] <= py + .1 and place[1] + 1 >= py - 1.7 and
                                    place[2] <= pz + .3 and place[2] + 1 >= pz - .3):
                                world.set(*place, HOTBAR[selected])

        if pygame.event.get_grab() and not inventory_open:
            keys = pygame.key.get_pressed()
            player.move(world, dt, keys)

        world.ensure_area(player.pos[0], player.pos[2])
        renderer.rebuild_dirty(world)
        renderer.render(player)

        # Pygame's 2D overlay is drawn after the OpenGL scene.
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Crosshair.
        pygame.draw.line(overlay, (255,255,255,230), (WIDTH//2-9, HEIGHT//2), (WIDTH//2+9, HEIGHT//2), 2)
        pygame.draw.line(overlay, (255,255,255,230), (WIDTH//2, HEIGHT//2-9), (WIDTH//2, HEIGHT//2+9), 2)

        # Hotbar.
        slot_w, slot_h = 58, 54
        start_x = WIDTH//2 - (slot_w * 8)//2
        ybar = HEIGHT - 70
        for i, block in enumerate(HOTBAR):
            x = start_x + i * slot_w
            pygame.draw.rect(overlay, (25,25,25,210), (x, ybar, slot_w-4, slot_h), border_radius=5)
            pygame.draw.rect(overlay, (245,245,245,255) if i == selected else (100,100,100,255),
                             (x, ybar, slot_w-4, slot_h), 3 if i == selected else 1, border_radius=5)
            c = tuple(int(v*255) for v in COLORS[block])
            pygame.draw.rect(overlay, c, (x+16, ybar+8, 22, 22), border_radius=3)
            draw_text(overlay, small, str(i+1), (x+5, ybar+35))
        draw_text(overlay, small, BLOCK_NAMES[HOTBAR[selected]], (WIDTH//2-45, ybar-22))

        if inventory_open:
            panel = pygame.Rect(WIDTH//2-230, HEIGHT//2-150, 460, 300)
            pygame.draw.rect(overlay, (25,25,35,235), panel, border_radius=12)
            pygame.draw.rect(overlay, (220,220,220,255), panel, 2, border_radius=12)
            draw_text(overlay, font, "INVENTORY - press 1-8 to select, E to close",
                      (panel.x+22, panel.y+20))
            for i, block in enumerate(HOTBAR):
                col, row = i % 4, i // 4
                x, y = panel.x+35+col*105, panel.y+85+row*85
                pygame.draw.rect(overlay, tuple(int(v*255) for v in COLORS[block]), (x,y,32,32))
                draw_text(overlay, small, f"{i+1}. {BLOCK_NAMES[block]}", (x+40,y+7))

        if debug:
            draw_text(overlay, small, f"XYZ: {player.pos[0]:.1f}, {player.pos[1]:.1f}, {player.pos[2]:.1f}", (12, 12))
            draw_text(overlay, small, f"Chunks: {len(world.chunks)} | FPS: {clock.get_fps():.0f} | Flying: {player.flying}", (12, 32))
            draw_text(overlay, small, "F toggles flight | F3 debug | Esc releases mouse | Enter captures", (12, 52))
        if time.time() < message_until:
            label = font.render(message, True, (255,255,255))
            overlay.blit(label, (WIDTH//2-label.get_width()//2, 18))

        # Blit overlay using pygame after switching out of the OpenGL framebuffer.
        # pygame's OPENGL display does not support normal Surface blits, so draw UI via
        # a temporary 2D OpenGL texture.
        rgba = pygame.image.tostring(overlay, "RGBA", True)
        if not hasattr(renderer, "hud_texture"):
            renderer.hud_texture = renderer.ctx.texture((WIDTH, HEIGHT), 4, rgba)
            renderer.hud_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        else:
            renderer.hud_texture.write(rgba)
        # A tiny fullscreen shader for the HUD.
        if not hasattr(renderer, "hud_program"):
            renderer.hud_program = renderer.ctx.program(
                vertex_shader="""#version 330
                in vec2 p; in vec2 uv; out vec2 v_uv;
                void main(){ v_uv=uv; gl_Position=vec4(p,0.0,1.0); }""",
                fragment_shader="""#version 330
                uniform sampler2D hud; in vec2 v_uv; out vec4 f;
                void main(){ f=texture(hud,v_uv); }"""
            )
            quad = np.array([-1,-1,0,0, 1,-1,1,0, 1,1,1,1,
                             -1,-1,0,0, 1,1,1,1, -1,1,0,1], dtype="f4")
            renderer.hud_vbo = renderer.ctx.buffer(quad.tobytes())
            renderer.hud_vao = renderer.ctx.vertex_array(renderer.hud_program,
                [(renderer.hud_vbo, "2f 2f", "p", "uv")])
        renderer.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        renderer.hud_texture.use(0)
        renderer.hud_program["hud"].value = 0
        renderer.hud_vao.render(moderngl.TRIANGLES)
        renderer.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        pygame.display.flip()

    world.save()
    renderer.close()
    if hasattr(renderer, "hud_vao"):
        renderer.hud_vao.release()
        renderer.hud_vbo.release()
        renderer.hud_program.release()
        renderer.hud_texture.release()
    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nVoxelCraft stopped with an error:")
        print(exc)
        raise

