# Complementos de IngePresupuestos

El catálogo que se ve en **Complementos ▸ Explorar** al pulsar **Sincronizar**.

Es un **directorio**, no una tienda: cada complemento está en el repositorio de su
autor. Aquí solo hay una **ficha** (`fichas/<id>.toml`) con la dirección del `.zip` y
su huella SHA-256.

## Publicar el tuyo

En IngePresupuestos: **Complementos ▸ Instalados ▸ ⋯ ▸ Publicar…** y sigue los
cuatro pasos. No hace falta saber Git. Necesitas una cuenta de GitHub, un
repositorio público tuyo y una licencia libre (GPL-3.0-or-later, MIT…) en
`complemento.json`.

A mano: sube el `.zip` a una versión (*release*) de tu repositorio, copia
[`PLANTILLA.toml`](PLANTILLA.toml) a `fichas/<id>.toml` y abre una *pull request*.

Un robot comprueba la dirección, la huella, la licencia y que el complemento sea
válido. **Lee el código, nunca lo ejecuta.** La primera ficha la aprueba una persona.

**Versión nueva:** sube `version` en `complemento.json` y cambia `descarga` y
`sha256` de tu ficha. Si la propone la cuenta que figura en ella y el robot no
encuentra nada que leer, **se publica sola**, como «Comunidad».

No publiques bases de precios ni datos de terceros sin permiso para distribuirlos.

Cómo se escribe uno:
[guía de complementos](https://github.com/ingelibre/ingepresupuestos/blob/main/docs/complementos.md).

## Revisado y Comunidad

Un complemento con código puede hacer lo mismo que el programa.

- **Revisado**: alguien que mantiene IngePresupuestos leyó **ese archivo exacto**
  (`revisados.toml`). Una versión nueva vuelve a «Comunidad».
- **Comunidad**: pasó la revisión automática; nadie lo leyó a fondo.

## Para quienes mantienen el catálogo

- **Aprobar:** mira el informe del robot en la *pull request* y pulsa **Merge**.
- **Marcar como revisado:** tras leer el código, pon su `sha256` en `revisados.toml`.
- **Retirar:** borra la ficha. Deja de ofrecerse; a quien lo tenga instalado no se le quita.

Las fichas y `catalogo.json` son de dominio público (CC0-1.0); `herramientas/`,
GPL-3.0-or-later. Cada complemento conserva su licencia.
