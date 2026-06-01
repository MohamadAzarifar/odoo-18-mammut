const JalaaliGregorianConverter = class {
	static div(a, b) {
		return ~~(a / b)
	}

	static mod(a, b) {
		return a - ~~(a / b) * b
	}

	static jalCal(jy) {
		// Jalaali years starting the 33-year rule.
		var breaks = [
				-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181,
				1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394,
				2456, 3178, 3211, 3244, 3277, 3310, 3343, 3376,
				3409, 3442, 3475, 3508, 3541, 3574, 3607, 3640,
				3673, 3706, 3739, 3772, 3805, 3838, 3871, 3904,
				3937, 3970, 4003, 4036, 4069, 4102, 4135, 4168,
				4201, 4234, 4267, 4300, 4333, 4366, 4399, 4432,
				4465, 4498, 4531, 4564, 4597, 4630, 4663, 4696,
				4729, 4762, 4795, 4828, 4861, 4894, 4927, 4960,
				4993, 5026, 5059, 5092, 5125, 5158, 5191, 5224,
				5257, 5290, 5323, 5356, 5389, 5422, 5455, 5488,
				5521, 5554, 5587, 5620, 5653, 5686, 5719, 5752,
				5785, 5818, 5851, 5884, 5917, 5950, 5983, 6016,
				6049, 6082, 6115, 6148, 6181, 6214, 6247, 6280,
				6313, 6346, 6379, 6412, 6445, 6478, 6511, 6544,
				6577, 6610, 6643, 6676, 6709, 6742, 6775, 6808,
				6841, 6874, 6907, 6940, 6973, 7006, 7039, 7072,
				7105, 7138, 7171, 7204, 7237, 7270, 7303, 7336,
				7369, 7402, 7435, 7468, 7501, 7534, 7567, 7600,
				7633, 7666, 7699, 7732, 7765, 7798, 7831, 7864,
				7897, 7930, 7963, 7996, 8029, 8062, 8095, 8128,
				8161, 8194, 8227, 8260, 8293, 8326, 8359, 8392,
				8425, 8458, 8491, 8524, 8557, 8590, 8623, 8656,
				8689, 8722, 8755, 8788, 8821, 8854, 8887, 8920,
				8953, 8986, 9019, 9052, 9085, 9118, 9151, 9184,
				9217, 9250, 9283, 9316, 9349, 9382, 9415, 9448,
				9481, 9514, 9547, 9580, 9613, 9646, 9679, 9712,
				9745, 9778, 9811, 9844, 9877, 9910, 9943, 9976
			],
			bl = breaks.length,
			gy = jy + 621,
			leapJ = -14,
			jp = breaks[0],
			jm, jump, leap, leapG, march, n, i

		if (jy < jp || jy >= breaks[bl - 1])
			throw new Error('Invalid Jalaali year ' + jy)

		// Find the limiting years for the Jalaali year jy.
		for (i = 1; i < bl; i += 1) {
			jm = breaks[i]
			jump = jm - jp
			if (jy < jm)
				break
			leapJ = leapJ + this.div(jump, 33) * 8 + this.div(this.mod(jump, 33), 4)
			jp = jm
		}
		n = jy - jp

		// Find the number of leap years from AD 621 to the beginning
		// of the current Jalaali year in the Persian calendar.
		leapJ = leapJ + this.div(n, 33) * 8 + this.div(this.mod(n, 33) + 3, 4)
		if (this.mod(jump, 33) === 4 && jump - n === 4)
			leapJ += 1

		// And the same in the Gregorian calendar (until the year gy).
		leapG = this.div(gy, 4) - this.div((this.div(gy, 100) + 1) * 3, 4) - 150

		// Determine the Gregorian date of Farvardin the 1st.
		march = 20 + leapJ - leapG

		// Find how many years have passed since the last leap year.
		if (jump - n < 6)
			n = n - jump + this.div(jump + 4, 33) * 33
		leap = this.mod(this.mod(n + 1, 33) - 1, 4)
		if (leap === -1) {
			leap = 4
		}

		return {
			leap: leap,
			gy: gy,
			march: march
		}
	}

	static g2d(gy, gm, gd) {
		var d = this.div((gy + this.div(gm - 8, 6) + 100100) * 1461, 4) +
			this.div(153 * this.mod(gm + 9, 12) + 2, 5) +
			gd - 34840408
		d = d - this.div(this.div(gy + 100100 + this.div(gm - 8, 6), 100) * 3, 4) + 752
		return d
	}

	static j2d(jy, jm, jd) {
		var r = this.jalCal(jy)
		return this.g2d(r.gy, 3, r.march) + (jm - 1) * 31 - this.div(jm, 7) * (jm - 7) + jd - 1
	}

	static d2g(jdn) {
		var j, i, gd, gm, gy
		j = 4 * jdn + 139361631
		j = j + this.div(this.div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
		i = this.div(this.mod(j, 1461), 4) * 5 + 308
		gd = this.div(this.mod(i, 153), 5) + 1
		gm = this.mod(this.div(i, 153), 12) + 1
		gy = this.div(j, 1461) - 100100 + this.div(8 - gm, 6)
		return {
			gy: gy,
			gm: gm,
			gd: gd
		}
	}

	static d2j(jdn) {
		var gy = this.d2g(jdn).gy // Calculate Gregorian year (gy).
			,
			jy = gy - 621,
			r = this.jalCal(jy),
			jdn1f = this.g2d(gy, 3, r.march),
			jd, jm, k

		// Find number of days that passed since 1 Farvardin.
		k = jdn - jdn1f
		if (k >= 0) {
			if (k <= 185) {
				// The first 6 months.
				jm = 1 + this.div(k, 31)
				jd = this.mod(k, 31) + 1
				return {
					jy: jy,
					jm: jm,
					jd: jd
				}
			} else {
				// The remaining months.
				k -= 186
			}
		} else {
			// Previous Jalaali year.
			jy -= 1
			k += 179
			if (r.leap === 1)
				k += 1
		}
		jm = 7 + this.div(k, 30)
		jd = this.mod(k, 30) + 1
		return {
			jy: jy,
			jm: jm,
			jd: jd
		}
	}

	static toJalaali(gy, gm, gd) {
		if (Object.prototype.toString.call(gy) === '[object Date]') {
			gd = gy.getDate()
			gm = gy.getMonth() + 1
			gy = gy.getFullYear()
		}
		return this.d2j(this.g2d(gy, gm, gd))
	}

	static toGregorian(jy, jm, jd) {
		return this.d2g(this.j2d(jy, jm, jd))
	}
};

luxon.Duration.normalizeUnit = function (unit) {
	var normalized = {
		year: "years",
		years: "years",
		quarter: "quarters",
		quarters: "quarters",
		month: "months",
		months: "months",
		week: "weeks",
		weeks: "weeks",
		day: "days",
		days: "days",
		hour: "hours",
		hours: "hours",
		minute: "minutes",
		minutes: "minutes",
		second: "seconds",
		seconds: "seconds",
		millisecond: "milliseconds",
		milliseconds: "milliseconds",
		////////// overrided //////////
		weekday: "weekdays",
		weekdays: "weekdays",
		weeknumber: "weekNumbers",
		weeksnumber: "weekNumbers",
		weeknumbers: "weekNumbers",
		weekyear: "weekYears",
		weekyears: "weekYears",
		ordinal: "ordinals",

		jyear: "jyears",
		jyears: "jyears",
		jquarter: "jquarters",
		jquarters: "jquarters",
		jmonth: "jmonths",
		jmonths: "jmonths",
		jweek: "jweeks",
		jweeks: "jweeks",
		jday: "jdays",
		jdays: "jdays",

		jweekday: "jweekdays",
		jweekdays: "jweekdays",
		jweeknumber: "jweekNumbers",
		jweeksnumber: "jweekNumbers",
		jweeknumbers: "jweekNumbers",
		jweekyear: "jweekYears",
		jweekyears: "jweekYears",
		jordinal: "jordinals",
		////////// ///////// //////////
	} [unit ? unit.toLowerCase() : unit];
	if (!normalized) throw new luxon.InvalidUnitError(unit);
	return normalized;
};


const originalFromObject = luxon.DateTime.fromObject;
luxon.DateTime.fromObject = function (...args) {
	args[0] = luxon.Duration.fromDurationLike(args[0]).values;

	if (args[0].hasOwnProperty("jyears") || args[0].hasOwnProperty("jmonths") || args[0].hasOwnProperty("jdays")) {
		var j_year = args[0].jyears ? args[0].jyears : 0;
		var j_month = args[0].jmonths ? args[0].jmonths : 1;
		var j_day = args[0].jdays ? args[0].jdays : 1;

		var gregorian_parts = JalaaliGregorianConverter.toGregorian(j_year, j_month, j_day);

		args[0].years = gregorian_parts.gy;
		args[0].months = gregorian_parts.gm;
		args[0].days = gregorian_parts.gd;

		delete args[0].jyears;
		delete args[0].jmonths;
		delete args[0].jdays;
	}
	return originalFromObject.call(this, ...args);
};

const originalFromFormat = luxon.DateTime.fromFormat;
luxon.DateTime.fromFormat = function (text, fmt, opts = {}) {
	if (fmt.includes("j")) {
		fmt = fmt.replace(/j/g, "");
		const year_tokens = ["yyyyyy", "yyyy", "yy", "y"];
		const month_tokens = ["LLLLL", "LLLL", "LLL", "LL", "L", "MMMMM", "MMMM", "MMM", "MM", "M"];
		const day_tokens = ["dd", "d"];

		var fmt_parts = {
			year: {
				token: "",
				index: -1
			},
			month: {
				token: "",
				index: -1
			},
			day: {
				token: "",
				index: -1
			},
			hour: {
				token: "HH",
				index: fmt.indexOf("HH")	
			},
			minute: {
				token: "mm",
				index: fmt.indexOf("mm")	
			},
			second: {
				token: "ss",
				index: fmt.indexOf("ss")	
			},
		};

		for (const token of year_tokens) {
			var index = fmt.indexOf(token);
			if (index != -1) {
				fmt_parts.year.token = token;
				fmt_parts.year.index = index;
				break;
			}
		}

		for (const token of month_tokens) {
			var index = fmt.indexOf(token);
			if (index != -1) {
				fmt_parts.month.token = token;
				fmt_parts.month.index = index;
				break;
			}
		}

		for (const token of day_tokens) {
			var index = fmt.indexOf(token);
			if (index != -1) {
				fmt_parts.day.token = token;
				fmt_parts.day.index = index;
				break;
			}
		}

		const text_parts = {
			year: parseInt(text.substring(fmt_parts.year.index, fmt_parts.year.index + fmt_parts.year.token.length), 10),
			month: parseInt(text.substring(fmt_parts.month.index, fmt_parts.month.index + fmt_parts.month.token.length), 10),
			day: parseInt(text.substring(fmt_parts.day.index, fmt_parts.day.index + fmt_parts.day.token.length), 10),
			hour: fmt_parts.hour.index != -1 ? parseInt(text.substring(fmt_parts.hour.index, fmt_parts.hour.index + fmt_parts.hour.token.length), 10) : 0,
			minute: fmt_parts.minute.index != -1 ? parseInt(text.substring(fmt_parts.minute.index, fmt_parts.minute.index + fmt_parts.minute.token.length), 10) : 0,
			second: fmt_parts.second.index != -1 ? parseInt(text.substring(fmt_parts.second.index, fmt_parts.second.index + fmt_parts.second.token.length), 10) : 0
		};

		if (text_parts.year < 1500) {
			return this.fromObject({
				jyear: text_parts.year,
				jmonth: text_parts.month,
				jday: text_parts.day,
				hour: text_parts.hour,
				minute: text_parts.minute,
				second: text_parts.second
			});
		} else {
			return this.fromObject({
				year: text_parts.year,
				month: text_parts.month,
				day: text_parts.day,
				hour: text_parts.hour,
				minute: text_parts.minute,
				second: text_parts.second
			});
		}


	} else {
		return originalFromFormat.call(this, text, fmt, opts);
	}
};

const reconstructors = [
	"set",
	"plus",
	"minus",
];

reconstructors.forEach((method) => {
	const originalMethod = luxon.DateTime.prototype[method];
	luxon.DateTime.prototype[method] = function (...args) {
		args[0] = luxon.Duration.fromDurationLike(args[0]).values;

		if (args[0].hasOwnProperty("jyears") || args[0].hasOwnProperty("jquarters") || args[0].hasOwnProperty("jmonths") || args[0].hasOwnProperty("jweeks") || args[0].hasOwnProperty("jdays")) {
			if (method === "set") {
				var j_new_year = args[0].jyears ? args[0].jyears : this.jyear;
				var j_new_month = args[0].jmonths ? args[0].jmonths : this.jmonth;
				var j_new_day = args[0].jdays ? args[0].jdays : this.jday;

				var gregorian_parts = JalaaliGregorianConverter.toGregorian(j_new_year, j_new_month, j_new_day);

				args[0].years = gregorian_parts.gy;
				args[0].months = gregorian_parts.gm;
				args[0].days = gregorian_parts.gd;
			} else { // method === "plus" || method === "minus"

				var delta_years = (args[0].jyears ? args[0].jyears : 0);
				var delta_months = (args[0].jmonths ? args[0].jmonths : 0) + (args[0].jquarters ? args[0].jquarters : 0) * 3;
				var delta_days = (args[0].jdays ? args[0].jdays : 0) + (args[0].jweeks ? args[0].jweeks : 0) * 7;

				if(method === "minus") {
					delta_years *= -1;
					delta_months *= -1;
				}

				while (this.jmonth + delta_months > 12) {
					delta_years += 1;
					delta_months -= 12;
				}

				while (this.jmonth + delta_months < 1) {
					delta_years -= 1;
					delta_months += 12;
				}

				var j_new_year = this.jyear + delta_years;
				var j_new_month = this.jmonth + delta_months;
				var j_current_day = this.jday;

				var temp_j_semi_new_date = luxon.DateTime.fromObject({
					jyear: j_new_year,
					jmonth: j_new_month,
					jday: 1
				});
				if (j_current_day > temp_j_semi_new_date.jdaysInMonth) {
					j_current_day = temp_j_semi_new_date.jdaysInMonth;
				}

				var semi_new_date_gregorian_parts = JalaaliGregorianConverter.toGregorian(j_new_year, j_new_month, j_current_day);
				var semi_new_date = this.set({
					year: semi_new_date_gregorian_parts.gy,
					month: semi_new_date_gregorian_parts.gm,
					day: semi_new_date_gregorian_parts.gd
				});

				args[0].days = delta_days + semi_new_date.diff(this).as("days");
			}

			delete args[0].jyears;
			delete args[0].jquarters;
			delete args[0].jmonths;
			delete args[0].jweeks;
			delete args[0].jdays;
		}
		return originalMethod.call(this, ...args);
	};
});

const Ofers = [
	"startOf",
	"endOf",
];

Ofers.forEach((method) => {
	const originalMethod = luxon.DateTime.prototype[method];
	luxon.DateTime.prototype[method] = function (unit, {
		useLocaleWeeks = false
	} = {}) {
		const normalizedUnit = luxon.Duration.normalizeUnit(unit);

		if (unit.includes("j")) {
			if (method === "startOf") {
				const o = {};
				switch (normalizedUnit) {
					case "jyears":
						o.jmonth = 1;
					case "jquarters":
					case "jmonths":
						o.jday = 1;
					case "jweeks":
					case "jdays":
						o.hour = 0;
					case "hours":
						o.minute = 0;
					case "minutes":
						o.second = 0;
					case "seconds":
						o.millisecond = 0;
						break;
				}

				if (normalizedUnit === "jweeks") {
					o.weekday = 3;
				}

				if (normalizedUnit === "jquarters") {
					var q = Math.ceil(this.jmonth / 3);
					o.jmonth = (q - 1) * 3 + 1;
				}
				return this.set(o);
			} else { // method === "endOf"
				var plus_args = {};
				plus_args[normalizedUnit] = 1;
				return this.plus(plus_args).startOf(normalizedUnit).minus(1);
			}
		} else {
			return originalMethod.call(this, unit, {
				useLocaleWeeks = false
			} = {});
		}
	};
});


Object.defineProperty(luxon.DateTime.prototype, 'jyear', {
	get: function () {
		var jalaali_parts = JalaaliGregorianConverter.toJalaali(this.year, this.month, this.day);
		return jalaali_parts.jy;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jmonth', {
	get: function () {
		var jalaali_parts = JalaaliGregorianConverter.toJalaali(this.year, this.month, this.day);
		return jalaali_parts.jm;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jday', {
	get: function () {
		var jalaali_parts = JalaaliGregorianConverter.toJalaali(this.year, this.month, this.day);
		return jalaali_parts.jd;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jquarter', {
	get: function () {
		return Math.ceil(this.jmonth / 3);
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jweekYear', {
	get: function () {
		// سال هفته جاری، بر اساس آخرین روز هفته است که ممکن است در سال بعد باشد
		var temp = this;
		while (temp.jweekday < 7) {
			temp = temp.plus({
				days: 1
			});
		}
		return temp.jyear;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jweekNumber', {
	get: function () {
		var first_friday_of_year = this.set({
			jmonth: 1,
			jday: 1
		});
		while (first_friday_of_year.jweekday < 7) {
			first_friday_of_year = first_friday_of_year.plus({
				days: 1
			});
		}

		var next_friday = this;
		while (next_friday.jweekday < 7) {
			next_friday = next_friday.plus({
				days: 1
			});
		}

		return Math.floor((next_friday.jordinal - first_friday_of_year.jordinal) / 7) + 1;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jweekday', {
	get: function () {
		var j = this.weekday + 2;
		return j <= 7 ? j : j - 7;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jordinal', {
	get: function () {
		return this.jmonth <= 7 ? (this.jmonth - 1) * 31 + this.jday : 186 + (this.jmonth - 7) * 30 + this.jday;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jmonthShort', {
	get: function () {
		var fa_months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
		return fa_months[this.jmonth - 1];
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jmonthLong', {
	get: function () {
		var fa_months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
		return fa_months[this.jmonth - 1];
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jisInLeapYear', {
	get: function () {
		return Math.floor(this.jyear / 33) in [1, 5, 9, 13, 17, 22, 26, 30] ? true : false;
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jdaysInMonth', {
	get: function () {
		var days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, this.jisInLeapYear ? 30 : 29];
		return days[this.jmonth - 1];
	}
});

Object.defineProperty(luxon.DateTime.prototype, 'jdaysInYear', {
	get: function () {
		return this.jisInLeapYear ? 366 : 365
	}
});


const originalToFormat = luxon.DateTime.prototype.toFormat;
luxon.DateTime.prototype.toFormat = function (fmt, opts = {}) {
	const jalaaliFormatRegex = /j\w+/g;
	const matches = fmt.match(jalaaliFormatRegex);

	if (matches) {
		for (const match of matches) {
			let replacement = "";

			switch (match) {
				case "jd":
					replacement = this.jday.toString();
					break;

				case "jdd":
					replacement = String(this.jday).padStart(2, "0");
					break;

				case "jL":
					// like 1
					replacement = this.jmonth.toString();
					break;

				case "jLL":
					// like 01, doesn't seem to work
					replacement = String(this.jmonth).padStart(2, "0");
					break;

				case "jLLL":
					// like Jan
					replacement = this.jmonthShort;
					break;

				case "jLLLL":
					// like January
					replacement = this.jmonthLong;
					break;

				case "jLLLLL":
					// like J
					replacement = this.jmonthLong[0];
					break;
					// months - format

				case "jM":
					// like 1
					replacement = this.jmonth.toString();
					break;

				case "jMM":
					// like 01
					replacement = String(this.jmonth).padStart(2, "0");
					break;

				case "jMMM":
					// like Jan
					replacement = this.jmonthShort;
					break;

				case "jMMMM":
					// like January
					replacement = this.jmonthLong;
					break;

				case "jMMMMM":
					// like J
					replacement = this.jmonthLong[0];
					break;
					// years

				case "jy":
					// like 2025
					replacement = this.jyear.toString();
					break;

				case "jyy":
					// like 25
					replacement = this.jyear.toString().slice(-2);
					break;

				case "jyyyy":
					// like 0025
					replacement = this.jyear.toString();
					break;

				case "jyyyyyy":
					// like 000025
					replacement = String(this.jyear).padStart(6, "0");
					break;

				case "jkk":
					replacement = this.jweekYear.toString().slice(-2);
					break

				case "jkkkk":
					replacement = String(this.jweekYear).padStart(4, "0");
					break;

				case "jW":
					replacement = this.jweekNumber.toString();
					break;

				case "jWW":
					replacement = String(this.jweekNumber).padStart(2, "0");
					break;

				case "jo":
					replacement = this.jordinal.toString();
					break;

				case "jooo":
					replacement = String(this.jordinal).padStart(3, "0");
					break;

				case "jq":
					// like 1
					replacement = this.jquarter.toString();
					break;

				case "jqq":
					// like 01
					replacement = String(this.jquarter).padStart(2, "0");
					break;

				case "jDDD":
					// like January 1, 2025
					replacement = `${this.jmonthLong} ${this.jday.toString()}, ${this.jyear.toString()}`;
					break;

				default:
					throw new Error(`Unsupported jalaali format token: ${match}`);
			}
			fmt = fmt.replace(match, replacement);
		}
	}

	var result = originalToFormat.call(this, fmt, opts);
	const en_jmonth_map = {
		"فروردین": "Farvardin",
		"اردیبهشت": "Ordibehesht",
		"خرداد": "Khordad",
		"تیر": "Tir",
		"مرداد": "Mordad",
		"شهریور": "Shahrivar",
		"مهر": "Mehr",
		"آبان": "Aban",
		"آذر": "Azar",
		"دی": "Dey",
		"بهمن": "Bahman",
		"اسفند": "Esfand"
	};
	const regex = new RegExp(Object.keys(en_jmonth_map).join('|'), 'g');
	return result.replace(regex, (matched) => en_jmonth_map[matched]);
}

const originalDiff = luxon.DateTime.prototype.diff;
luxon.DateTime.prototype.diff = function (otherDateTime, unit = "milliseconds", opts = {}) {
	if (unit.includes("j")) {
		unit = unit.replace("j", "");
	}
	return originalDiff.call(this, otherDateTime, unit, opts);
};