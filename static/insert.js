/* globals WORDLIST, forge */

const getForm = () => document.getElementById('InsertForm')

const getRandomValues = mod => {
    // http://caniuse.com/#feat=getrandomvalues
    if (window.crypto && window.crypto.getRandomValues) {
        const result = new Uint32Array(1)
        window.crypto.getRandomValues(result)
        return result[0] % mod
    } else if (window.msCrypto && window.msCrypto.getRandomValues) {
        const result = new Uint32Array(1)
        window.msCrypto.getRandomValues(result)
        return result[0] % mod
    } else {
        return Math.floor(Math.random() * mod)
    }
}

const generateHumanReadableRandomPassword = event => {
    event.preventDefault()
    const form = getForm()
    const separators = ['.', '-', '_', '+']
    const s = separators[getRandomValues(separators.length)]
    const w = () => {
        return WORDLIST[getRandomValues(WORDLIST.length)]
    }
    const pass = `${w()}${s}${w()}${s}${w()}${s}${w()}${s}${w()}`
    form.elements.secret.value = pass
}

const generateRandomPassword = event => {
    event.preventDefault()
    const form = getForm()
    const generate = length => {
        return Array.apply(null, { length: length })
            .map(function() {
                let result
                for (;;) {
                    result = String.fromCharCode(getRandomValues(256))
                    if (/[a-zA-Z0-9_\-+.]/.test(result)) {
                        return result
                    }
                }
            }, this)
            .join('')
    }
    form.elements.secret.value = generate(32)
}

const createSecret = event => {
    event.preventDefault()
    const form = getForm()
    const publicKey = forge.pki.publicKeyFromPem(form.elements.public_key.value)
    const msg = publicKey.encrypt(form.elements.secret.value, 'RSA-OAEP')

    if (msg) {
        document.body.classList.add('wait')
        const elements = ['create', 'generator1', 'generator2']
        elements.map(function(x) {
            form.elements[x].setAttribute('disabled', true)
        })
        form.elements.secret.value = forge.util.encode64(msg)
        form.elements.secret.setAttribute('readonly', true)
        form.elements.encrypted.checked = true
        form.submit()
    } else {
        alert('error while encrypting')
    }
}

const updateUI = event => {
    const form = getForm()
    const counter = form.querySelector('.counter')
    const maxbytes = 245
    const action =
        event.target.value === '' ? 'removeAttribute' : 'setAttribute'
    form.elements.generator1[action]('disabled', true)
    form.elements.generator2[action]('disabled', true)
    counter.innerHTML = `${event.target.value.length}/${maxbytes}`
    if (event.target.value.length > maxbytes) {
        counter.classList.add('warning')
    } else if (counter.classList.contains('warning')) {
        counter.classList.remove('warning')
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const form = getForm()
    // bind events
    form.elements.generator1.onclick = generateHumanReadableRandomPassword
    form.elements.generator2.onclick = generateRandomPassword
    form.elements.create.onclick = createSecret
    form.elements.secret.onkeyup = updateUI
    form.elements.secret.onchange = updateUI
    // enable buttons
    form.elements.generator1.removeAttribute('disabled')
    form.elements.generator2.removeAttribute('disabled')
})
