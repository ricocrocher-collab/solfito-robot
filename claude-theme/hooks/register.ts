import type { Register, ThemeSetArgs } from 'claude-code'

import { makeColors } from './make-colors.js'

// Couleurs de l'appli Solfito (site/css/style-NNN.css) : fond lavande le jour, nuit violette le soir.
const { theme, problems } = makeColors({
  label: 'Solfito',
  roles: { accent: '#5B5BD6', danger: '#E0433F', success: '#2FA35A', warning: '#F2C12E', pro: '#F28C28' },
  light: {
    gray: {
      anchors: {
        'surface-0': '#F3F1FF',
        'surface-1': '#F8F7FF',
        'surface-2': '#FFFFFF',
        'surface-3': '#FFFFFF',
        'text-primary': '#231D5A',
        'text-secondary': '#3F3A7A',
        'text-muted': '#5E5A94',
      },
    },
  },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#17143A',
        'surface-1': '#1C1844',
        'surface-2': '#221E4F',
        'surface-3': '#262257',
        'text-primary': '#F1EFFF',
        'text-secondary': '#CFCBF0',
        'text-muted': '#A9A5D6',
      },
    },
  },
})

const LOOK: ThemeSetArgs = { colors: theme }

// Le jaune doré de Solfito : tes messages dans une bulle dorée.
const STYLED: ThemeSetArgs = {
  ...LOOK,
  style: {
    UserMessage: { backgroundColor: '#F2C12E', color: '#231D5A', radius: 18, paddingX: 14, paddingY: 10 },
  },
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const unpainted = problems.find(line => line.startsWith("Desktop won't paint"))

    if (unpainted !== undefined) {
      $.ui.toast(unpainted)
    }
    let set: Awaited<ReturnType<typeof $.theme.set>>

    try {
      set = await $.theme.set(STYLED)
    } catch (error) {
      $.ui.log(String(error))
      set = await $.theme.set(LOOK)
    }

    if (!set.isDrawn) {
      $.ui.status(set.reason)
    }

    return next(e)
  })
}
